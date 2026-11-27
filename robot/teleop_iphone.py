"""Teleoperate the arm with a hand-held iPhone (iMuninn in AR mode), and record episodes while doing it.

    uv run python robot/teleop_iphone.py --leader <name or address>          # real arm: plan only, nothing moves
    uv run python robot/teleop_iphone.py --leader <name or address> --yes    # real arm
    uv run python robot/teleop_iphone.py --sim --keys "1:space,3:r,14:r,15:q"   # simulator, a scripted hand

The hand-held phone (the leader) is mapped onto the phone on the arm's tool (the follower):

- orientation, absolute: the follower phone takes the leader's attitude. Both phones' frames are the AR camera frame
  (x to the right of the landscape picture, y up, z out of the screen), so holding the leader the way the follower
  is mounted keeps the tool where it is. Roll and pitch are absolute through gravity. The heading has no common
  reference (an AR session starts with an arbitrary one): it is aligned the first time you engage, so that
  engaging does not turn the tool about the vertical; `y` aligns it again while disengaged.
- position, relative: while engaged, the follower phone moves by what the leader moved since engaging, times
  --scale. Disengage, move your hand back, engage again to reach further (a clutch).

--point tip moves the tool tip by the leader's translation instead and turns the tool about its tip: the tip
then stays put when you only rotate the phone.

The leader must run iMuninn in AR mode with the pose stream on (`imuninn profile apply teleop <address>`); its
configuration is not changed here, its capture session is started if it is off. The arm stops following
(disengages and holds) when the pose is older than 0.25 s, AR tracking is not normal, or the pose jumps.

Engaging: the status line shows how far the leader's attitude is from the follower phone's ("apart"). Engaging is
refused above --max-engage-angle (10 deg by default): hold the leader like the phone on the tool first. What
difference is left is taken up at --catch-up-turn (20 deg/s) before the tool turns at full speed.

Keys: see robot/teleop.py, plus  y  align the heading again (disengaged only).
Recorded in every episode in addition: `leader_pose` (position and quaternion x, y, z, w as iMuninn sent them,
AR world frame), `leader_age` (seconds since that pose was captured) and `leader_heading` (rad: the turn about the
vertical that takes the AR world into the arm's frame, as aligned).
"""

from __future__ import annotations

import argparse
import math
import sys
import threading
import time
from pathlib import Path

import numpy as np
import sharklog

sys.path.insert(0, str(Path(__file__).resolve().parent))
from teleop import Source, Teleop, add_arguments  # noqa: E402

A_ZUP = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])  # AR world (y up) -> z up
MAX_AGE = 0.25  # s: older poses are not followed
MAX_JUMP = 0.05  # m between two poses: AR relocalised


def quat_to_matrix(x: float, y: float, z: float, w: float) -> np.ndarray:
    n = math.sqrt(x * x + y * y + z * z + w * w)
    x, y, z, w = x / n, y / n, z / n, w / n
    return np.array(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ]
    )


def rot_z(a: float) -> np.ndarray:
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]])


def heading_between(r_from: np.ndarray, r_to: np.ndarray) -> float:
    """The turn about the vertical that brings ``r_from`` closest to ``r_to``."""
    d = r_to @ r_from.T
    return math.atan2(d[1, 0] - d[0, 1], d[0, 0] + d[1, 1])


class PhoneLeader:
    """Latest pose of the hand-held phone."""

    def __init__(self, target: str) -> None:
        import imuninn
        from imuninn.proto import imuninn_pb2 as pb

        self._pb = pb
        self.dev = imuninn.connect(target, timeout=10)
        mode = {pb.SESSION_MODE_AR: 'ar', pb.SESSION_MODE_CAMERA: 'camera'}.get(self.dev.config.mode)
        if mode != 'ar':
            host = target
            self.dev.close()
            raise RuntimeError(
                f'the leader phone is in {mode} mode; it must be in AR mode with the pose stream on: '
                f'uv run imuninn profile apply teleop {host}'
            )
        self._lock = threading.Lock()
        self._latest = None
        self.started = False
        self.dev.on('ar_pose', self._on_pose)
        if not self._wait(2.0):
            self.dev.start()
            self.started = True
            if not self._wait(8.0):
                self.dev.close()
                raise RuntimeError('the leader phone sends no poses (is the ar_pose stream enabled?)')

    def _wait(self, timeout: float) -> bool:
        t_end = time.monotonic() + timeout
        while time.monotonic() < t_end:
            if self._latest is not None:
                return True
            time.sleep(0.02)
        return False

    def _on_pose(self, s) -> None:
        t = self.dev.to_pc_time(s.header.device_time_ns)
        pose = np.array(
            [
                s.position.x,
                s.position.y,
                s.position.z,
                s.orientation.x,
                s.orientation.y,
                s.orientation.z,
                s.orientation.w,
            ]
        )
        with self._lock:
            self._latest = (t, pose, s.tracking == self._pb.TRACKING_STATE_NORMAL)

    def latest(self):
        """(age in seconds, pose [x, y, z, qx, qy, qz, qw] in the AR world, tracking normal)."""
        with self._lock:
            t, pose, ok = self._latest
        return time.time() - t, pose, ok

    def close(self) -> None:
        try:
            if self.started:
                self.dev.stop()
        finally:
            self.dev.close()


class ScriptedLeader:
    """A hand that draws a slow circle and tilts a little: for the simulator and the tests."""

    def __init__(self, clock, start_rot_ar: np.ndarray, tilt_deg: float = 10.0) -> None:
        self.clock, self.r0, self.tilt = clock, start_rot_ar, math.radians(tilt_deg)
        self.t0 = clock()

    def latest(self):
        t = self.clock() - self.t0
        w = 2 * math.pi / 8.0
        p = np.array(
            [0.3 + 0.05 * math.sin(w * t), 1.2 + 0.02 * math.sin(2 * w * t), -0.4 + 0.05 * (1 - math.cos(w * t))]
        )
        tilt = self.tilt * math.sin(w * t)
        c, s = math.cos(tilt), math.sin(tilt)
        r = self.r0 @ np.array([[1, 0, 0], [0, c, -s], [0, s, c]])  # nod about the phone's x axis
        # matrix -> quaternion
        qw = math.sqrt(max(0.0, 1 + r[0, 0] + r[1, 1] + r[2, 2])) / 2
        q = np.array(
            [(r[2, 1] - r[1, 2]) / (4 * qw), (r[0, 2] - r[2, 0]) / (4 * qw), (r[1, 0] - r[0, 1]) / (4 * qw), qw]
        )
        return 0.0, np.r_[p, q], True

    def restart(self) -> None:
        """Begin the script now: the hand is level and at rest at this moment."""
        self.t0 = self.clock()

    def close(self) -> None:
        pass


class IPhoneSource(Source):
    name = 'iPhone'
    kind = 'pose'
    keys_help = '   y = align heading'

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.leader = None
        self.psi: float | None = None  # heading of the AR world in the arm's frame
        self.p_ref = self.c_ref = None
        self.p_prev = None
        self.pose = np.zeros(7)
        self.age = 0.0
        self.apart = float('nan')  # deg between the leader's attitude and the follower phone's
        self.catching = False

    def plan(self) -> list[str]:
        a = self.args
        return [
            f'leader phone: {"scripted (simulator)" if a.sim and not a.leader else a.leader}; the {"tool tip" if a.point == "tip" else "follower phone"} '
            f'follows its translation x{a.scale:g}, the follower phone takes its attitude',
            "engaging for the first time aligns the heading: the tool does not turn about the vertical, but it tilts to the leader's roll and pitch",
        ]

    # geometry of the follower phone on the tool
    def open(self, app: Teleop) -> None:
        arm = app.arm
        phone = arm.tool.extra.get('phone')
        if not phone:
            raise RuntimeError("the tool config has no `phone` section (the follower phone's camera frame)")
        placement = arm.model.model.frames[arm.model.tcp_frame_id].placement  # tool frame in link6
        r_l_tcp, p_l_tcp = np.array(placement.rotation), np.array(placement.translation)
        self.r_tool_cam = r_l_tcp.T @ np.asarray(phone['camera_rot'], dtype=float)
        self.v_tool_cam = r_l_tcp.T @ (np.asarray(phone['camera_xyz'], dtype=float) - p_l_tcp)
        if self.args.sim and not self.args.leader:
            # hold the scripted phone the way the follower phone sits at home, turned by an arbitrary heading
            _, r_tcp = arm.model.fk(np.asarray(arm.tool.home, dtype=float))
            self.leader = ScriptedLeader(
                arm.now, A_ZUP.T @ rot_z(math.radians(40.0)) @ r_tcp @ self.r_tool_cam, self.args.sim_tilt
            )
        else:
            self.leader = PhoneLeader(self.args.leader)

    def close(self) -> None:
        if self.leader is not None:
            self.leader.close()

    def _read(self) -> str | None:
        self.age, self.pose, ok = self.leader.latest()
        if self.age > MAX_AGE:
            return f"the leader's pose is {self.age:.2f} s old"
        if not ok:
            return 'AR tracking on the leader is not normal'
        return None

    def _leader_in_base(self) -> tuple[np.ndarray, np.ndarray]:
        r = rot_z(self.psi) @ A_ZUP
        return r @ self.pose[:3], r @ quat_to_matrix(*self.pose[3:])

    def _control_point(self, app: Teleop) -> np.ndarray:
        pos, rot = app.tcp_now()
        return pos if self.args.point == 'tip' else pos + rot @ self.v_tool_cam

    def _heading_now(self, app: Teleop) -> float:
        _, rot = app.tcp_now()
        return heading_between(A_ZUP @ quat_to_matrix(*self.pose[3:]), rot @ self.r_tool_cam)

    def _align(self, app: Teleop) -> None:
        self.psi = self._heading_now(app)

    def _apart(self, app: Teleop) -> float:
        """Angle (deg) between the leader's attitude, mapped, and the follower phone's as commanded now."""
        psi = (
            self.psi if self.psi is not None else self._heading_now(app)
        )  # before the first engage: as it would be aligned
        _, rot = app.tcp_now()
        r_cam = rot_z(psi) @ A_ZUP @ quat_to_matrix(*self.pose[3:])
        return math.degrees(math.acos(float(np.clip((np.trace((rot @ self.r_tool_cam).T @ r_cam) - 1) / 2, -1.0, 1.0))))

    def engage(self, app: Teleop) -> str | None:
        if isinstance(self.leader, ScriptedLeader) and not app.engaged and self.p_ref is None:
            self.leader.restart()  # simulator: the scripted hand starts from the follower's attitude
        why = self._read()
        if why:
            return why
        self.apart = self._apart(app)
        if self.apart > self.args.max_engage_angle:
            return (
                f"the leader is {self.apart:.0f} deg away from the follower phone's attitude (limit {self.args.max_engage_angle:g}): "
                'hold it like the phone on the tool'
                + ('' if self.psi is None else ', or press y to align the heading again')
            )
        if self.psi is None:
            self._align(app)
        p, _ = self._leader_in_base()
        self.p_ref, self.c_ref, self.p_prev = p, self._control_point(app), p
        self.catching = True
        app.cart.limits.max_ang_speed = math.radians(self.args.catch_up_turn)  # take up the difference slowly
        return None

    def target(self, app: Teleop):
        why = self._read()
        if why:
            return why
        p, r_cam = self._leader_in_base()
        if np.linalg.norm(p - self.p_prev) > MAX_JUMP:
            return "the leader's pose jumped"
        self.p_prev = p
        self.apart = self._apart(app)
        if self.catching and self.apart < 2.0:
            self.catching = False
            app.cart.limits.max_ang_speed = math.radians(self.args.max_turn)
        wanted = r_cam @ self.r_tool_cam.T
        r_tcp = app.cart.limits.clip_orientation(wanted)  # the position below must fit the attitude the arm will take
        c = self.c_ref + self.args.scale * (p - self.p_ref)
        tip = self.args.point == 'tip'
        return (
            (c if tip else c - r_tcp @ self.v_tool_cam),
            r_tcp,
            wanted,
            (lambda r: c if tip else c - r @ self.v_tool_cam),
        )

    def key(self, key: str, app: Teleop) -> bool:
        if key != 'y':
            return False
        if app.engaged:
            sharklog.info('disengage before aligning the heading')
        elif self._read() is None:
            self._align(app)
            sharklog.info(f'heading aligned ({math.degrees(self.psi):+.0f} deg)')
        else:
            sharklog.info('no usable pose from the leader')
        return True

    def idle(self, app: Teleop) -> None:
        self.apart = self._apart(app) if self._read() is None else float('nan')

    def streams(self) -> dict[str, np.ndarray]:
        return {
            'leader_pose': self.pose,
            'leader_age': np.array([self.age]),
            'leader_heading': np.array([self.psi if self.psi is not None else np.nan]),
        }

    def status(self) -> str:
        why = self._read() if self.leader is not None else 'no leader'
        if why is not None:
            return f'leader: {why}'
        return f'leader ok, {self.apart:.0f} deg apart' + (' (catching up)' if self.catching else '')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--leader', help='the hand-held phone: iMuninn name, host or host:port')
    ap.add_argument('--scale', type=float, default=1.0, help='tool translation per leader translation')
    ap.add_argument(
        '--point',
        choices=('phone', 'tip'),
        default='phone',
        help="what follows the leader's translation and stays put when it only turns",
    )
    ap.add_argument(
        '--max-engage-angle',
        type=float,
        default=10.0,
        help="refuse to engage when the leader's attitude is further than this from the follower phone's (deg)",
    )
    ap.add_argument(
        '--catch-up-turn',
        type=float,
        default=20.0,
        help='turning speed while the tool takes up the difference left at engaging (deg/s)',
    )
    ap.add_argument('--sim-tilt', type=float, default=10.0, help='simulator: how far the scripted hand nods (deg)')
    add_arguments(ap)
    args = ap.parse_args()
    if not args.leader and not args.sim:
        print(
            "REFUSED: --leader is needed (the hand-held phone's iMuninn name or address; `uv run imuninn list` shows the phones)"
        )
        return 2
    if not 0.1 <= args.scale <= 3.0:
        print('REFUSED: --scale between 0.1 and 3')
        return 2
    return Teleop(IPhoneSource(args), args).run()


if __name__ == '__main__':
    sys.exit(main())
