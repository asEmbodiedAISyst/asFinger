"""What the teleoperation tools share: the arm's side of it, the keys, the recording.

Not run by itself: see robot/teleop_iphone.py and robot/teleop_star.py. A tool provides a Source (where the
operator's commands come from) and calls run().

Keys (no Enter needed):
    space  engage / disengage: only while engaged does the arm follow the operator
    r      start an episode / stop and save it          x  throw the last episode away
    f      the episode failed: stop and save it marked `success: false` (or mark the last saved one)
    h      disengage and go back to the home pose       q  quit: home, fold, torque off
A source can add keys of its own.

What the arm's side does, whatever the source:
- starts from the folded pose or home, goes to the tool's home pose, and follows only while engaged;
- lets the tool go as far as the hardware allows (the owner's wish: the workspace is small as it is). What stops it
  is geometry, not fixed angles: the joints' limits; the box of calibration/workspace.yaml for the joint centres,
  the tool tip and the phone on the tool; the table (tip at least --z-min, phone at least --phone-clear above it);
  and the arm itself (phone and rod at least --arm-clear from the base column, upper arm and forearm).
  --max-tilt and --max-heading are only outer bounds. The position comes first: when the attitude asked for
  cannot be taken, the tool keeps the attitude it has and follows the position, and if that attitude is in the
  way as well it swings back towards vertical. The status line says what is holding it back;
- limits the speed (--max-speed, --max-joint-speed);
- disengages by itself when the source goes stale or jumps, and holds;
- records, while an episode runs, the arm's servo log, both phones, and the streams `tcp_target` (commanded tool
  pose: position and rotation matrix by rows), `q_target` (commanded joint angles), `engaged`, `limited` (0 free,
  else the sum of 1 tilt bound, 2 heading bound, 4 box of the tip, 8 phone above the table, 16 attitude not
  possible there, 32 position not possible) and the source's own.
Messages go through sharklog (robot/log.py), with a live status line under them.
A failure of the arm (stall, temperature, lost bus) leaves it holding where it is: `robot/arm release` ends that.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import sharklog

sys.path.insert(0, str(Path(__file__).resolve().parent))
import log  # noqa: E402
from arm_move import go_home, load_workspace, start_pose, table_height, violation  # noqa: E402
from arm_touch_table import lowest_point  # noqa: E402
from episode import DATA, ROOT  # noqa: E402
from rebot_control import Arm  # noqa: E402
from rebot_control.cartesian import CartesianLimits  # noqa: E402
from rebot_control.pose import limit_tilt, tilt_angle, yaw_of  # noqa: E402

from record import Keys, Session  # noqa: E402

LIMIT_NAMES = {
    1: 'tilt bound',
    2: 'heading bound',
    4: 'edge of the box',
    8: 'phone near the table',
    16: 'attitude not possible here (position comes first)',
    32: 'position not possible',
}


class Source:
    """Where the operator's commands come from. `kind` is "pose" (tool pose targets) or "joints" (joint targets)."""

    name = 'source'
    kind = 'pose'
    keys_help = ''

    def plan(self) -> list[str]:
        """Lines for the plan printed before anything moves."""
        return []

    def open(self, app: Teleop) -> None:
        pass

    def close(self) -> None:
        pass

    def engage(self, app: Teleop) -> str | None:
        """Called when the operator engages. Return why not, or None to go ahead."""
        return None

    def target(self, app: Teleop):
        """The command for this cycle while engaged: (position, rotation[, rotation wanted before limits[, function
        giving the position for another rotation]]) or joint angles; a str says why there is none."""
        raise NotImplementedError

    def key(self, key: str, app: Teleop) -> bool:
        return False

    def idle(self, app: Teleop) -> None:
        """Called every cycle while disengaged (e.g. to keep the status line current)."""

    def streams(self) -> dict[str, np.ndarray]:
        """Extra rows to record this cycle."""
        return {}

    def status(self) -> str:
        return ''


def add_arguments(ap: argparse.ArgumentParser) -> None:
    ap.add_argument('--task', default='teleop', help='short name of the task; goes into the episode folder names')
    ap.add_argument(
        '--instruction',
        default='',
        help="the task in words, as a language instruction (into every episode's meta.yaml)",
    )
    ap.add_argument('--operator', default='', help='who operates (free text, into meta.yaml)')
    ap.add_argument(
        '--cams', help="cameras to record: 'top,wrist' (default on the real arm) or 'none' (default in the simulator)"
    )
    ap.add_argument('--z-min', type=float, default=0.010, help='lowest height of the tool above the table (m)')
    ap.add_argument('--z-max', type=float, default=0.35, help='highest tool tip (m, arm frame)')
    ap.add_argument(
        '--arm-clear',
        type=float,
        default=0.07,
        help='closest the phone and the rod may come to the centre lines of the base column, upper arm and forearm (m)',
    )
    ap.add_argument(
        '--max-tilt',
        type=float,
        default=85.0,
        help='outer bound on the angle of the rod from vertical (deg), at most 89',
    )
    ap.add_argument(
        '--max-heading',
        type=float,
        default=180.0,
        help="outer bound on the tool's heading away from straight ahead (deg); 180 = none",
    )
    ap.add_argument(
        '--phone-clear', type=float, default=0.015, help='lowest height of the phone on the tool above the table (m)'
    )
    ap.add_argument('--max-speed', type=float, default=0.15, help='tool speed limit (m/s), at most 0.25')
    ap.add_argument('--max-turn', type=float, default=60.0, help='tool turning speed limit (deg/s)')
    ap.add_argument('--max-joint-speed', type=float, default=60.0, help='joint speed limit for joint sources (deg/s)')
    ap.add_argument(
        '--table-z', type=float, help='table height in the arm frame (m); default: calibration/table.yaml, simulator 0'
    )
    ap.add_argument(
        '--end', choices=('fold', 'hold'), default='fold', help='at quit: fold and torque off, or keep holding at home'
    )
    ap.add_argument('--sim', action='store_true')
    ap.add_argument(
        '--keys', help="scripted keys for tests and the simulator: 'seconds:key,...' (keys: space r f x h q ...)"
    )
    ap.add_argument('--yes', action='store_true', help='real arm: actually move (default: print the plan only)')
    ap.add_argument('--tool', default=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'))
    ap.add_argument('--calibration', default=str(ROOT / 'calibration' / 'b601_rs.yaml'))
    ap.add_argument('--workspace', default=str(ROOT / 'calibration' / 'workspace.yaml'))
    ap.add_argument('--root', default=str(DATA), help='where the episodes go')


class Teleop:
    def __init__(self, source: Source, args: argparse.Namespace) -> None:
        self.source, self.args = source, args
        self.arm = None
        self.cart = None
        self.session: Session | None = None
        self.engaged = False
        self.q_cmd: np.ndarray | None = None
        self.table = 0.0
        self.message = ''
        self.limited = 0
        self.corners = np.zeros((0, 3))  # corners of the phone on the tool, in the tool frame
        self.why = ''  # why the last pose was not allowed
        self._approach = False

    # -- helpers for sources
    def lowest(self, q: np.ndarray) -> float:
        """Height above the table of the lowest point of the tool: the rod tip or a corner of the phone."""
        low = lowest_point(self.arm.model, q, 0.0)[2]
        if len(self.corners):
            pos, rot = self.arm.tcp_pose(q)
            low = min(low, float((pos + self.corners @ rot.T)[:, 2].min()))
        return low - self.table

    def tcp_now(self) -> tuple[np.ndarray, np.ndarray]:
        """The commanded tool pose."""
        return self.cart.pose() if self.source.kind == 'pose' else self.arm.tcp_pose(self.q_cmd)

    def allowed(self, q: np.ndarray) -> str | None:
        """Why the arm may not take the joint angles ``q``, or None: box, table, and the tool against the arm itself."""
        arm, a = self.arm, self.args
        why = violation(arm.model, q, self.lo, self.hi)
        if why:
            return why
        joints = arm.model.link_positions(q)
        pos, rot = arm.tcp_pose(q)
        phone = pos + self.corners @ rot.T
        if len(phone):
            if phone[:, 2].min() < self.table + a.phone_clear - 0.002:
                return 'phone too close to the table'
            if (phone[:, :2] < self.lo[:2]).any() or (phone > self.hi).any():
                return 'phone outside the box'
        tool = np.vstack(
            [phone, pos - np.outer(np.linspace(0.0, 0.10, 6), rot[:, 2])]
        )  # and the outer 10 cm of the rod
        for name, p0, p1 in (
            ('base', np.zeros(3), joints[1]),
            ('upper arm', joints[1], joints[2]),
            ('forearm', joints[2], joints[2] + 0.75 * (joints[3] - joints[2])),
        ):
            d = p1 - p0
            t = np.clip((tool - p0) @ d / max(float(d @ d), 1e-12), 0.0, 1.0)
            if np.linalg.norm(tool - (p0 + np.outer(t, d)), axis=1).min() < a.arm_clear:
                return f'tool too close to the {name}'
        return None

    def disengage(self, why: str = '') -> None:
        if self.engaged:
            self.engaged = False
            (sharklog.warning if why else sharklog.info)('disengaged' + (f': {why}' if why else ''))

    # -- one control cycle
    def _follow_pose(self, target) -> None:
        lim, cart = self.cart.limits, self.cart
        pos, rot = np.array(target[0], dtype=float), np.asarray(target[1], dtype=float)
        wanted = np.asarray(target[2], dtype=float) if len(target) > 2 else rot  # the attitude before any limit
        pos_for = target[3] if len(target) > 3 else None  # tip position for another attitude
        flags = 0
        if lim.max_tilt_deg is not None and math.degrees(tilt_angle(wanted, lim.tilt_axis)) > lim.max_tilt_deg + 0.5:
            flags |= 1
        if lim.max_yaw_deg is not None and abs(math.degrees(yaw_of(wanted))) > lim.max_yaw_deg + 0.5:
            flags |= 2
        rot = lim.clip_orientation(rot)
        if not lim.contains(pos):
            flags |= 4
        if len(self.corners):  # lift the tool as far as the phone needs, for the attitude it will have
            need = self.table + self.args.phone_clear - float((self.corners @ rot.T)[:, 2].min())
            if pos[2] < need:
                pos[2] = need
                flags |= 8

        # Try the pose the controller would step to; if the arm cannot or may not take it, keep the attitude it has
        # and follow the position alone; if that fails too, hold. (Checked beforehand: one command per cycle.)
        def lifted(position: np.ndarray, rotation: np.ndarray) -> np.ndarray:
            if len(self.corners):
                position[2] = max(
                    position[2], self.table + self.args.phone_clear - float((self.corners @ rotation.T)[:, 2].min())
                )
            return position

        def possible(rotation) -> bool:
            p_next, r_next, _ = cart.limit(pos, rotation)
            res = cart.ik.solve(p_next, r_next, cart.q_cmd, max_iters=cart.ik_iters)
            self.why = (
                'no joint solution (a joint limit, or out of reach)' if not res.success else (self.allowed(res.q) or '')
            )
            return not self.why

        if possible(rot):
            st = cart.step(pos, rot)
        else:
            flags |= 16
            first = self.why
            if pos_for is not None:  # where the tip has to be for the attitude the tool keeps
                pos = lifted(np.array(pos_for(cart.rot), dtype=float), cart.rot)
            if possible(None):
                st = cart.step(pos, None)
                self.why = first
            else:
                # the attitude it has blocks the way too (a wrist joint at its limit): the position comes first, so
                # let the rod swing back towards vertical as far as one cycle allows
                upright = limit_tilt(cart.rot, 0.0, lim.tilt_axis)
                r_next = cart.limit(cart.pos, upright)[1]
                if pos_for is not None:
                    pos = lifted(np.array(pos_for(r_next), dtype=float), r_next)
                if possible(upright):
                    st = cart.step(pos, upright)
                    self.why = first
                else:
                    flags |= 32
                    st = cart.hold()
        self.q_cmd, self.limited = st.q, flags

    def _follow_joints(self, q_des: np.ndarray) -> str | None:
        arm, a = self.arm, self.args
        q_des = np.clip(np.asarray(q_des, dtype=float), arm.model.lower, arm.model.upper)
        speed = math.radians(15.0 if self._approach else a.max_joint_speed)
        step = np.clip(q_des - self.q_cmd, -speed * arm.dt, speed * arm.dt)
        if self._approach and np.abs(q_des - self.q_cmd).max() < math.radians(2.0):
            self._approach = False
        q_new = self.q_cmd + step
        why = self.allowed(q_new)
        if why is None:
            self.q_cmd = q_new
        arm.command_joint(self.q_cmd)
        arm.check_stall()
        return why

    def _cycle(self) -> None:
        arm, src = self.arm, self.source
        blocked = None
        self.limited = 0
        if self.engaged:
            target = src.target(self)
            if isinstance(target, str):
                self.disengage(target)
        if self.engaged:
            if src.kind == 'pose':
                self._follow_pose(target)
            else:
                blocked = self._follow_joints(target)
        else:
            src.idle(self)
            if src.kind == 'pose':
                self.q_cmd = self.cart.hold().q
            else:
                arm.command_joint(self.q_cmd)
        low = self.lowest(arm.q())
        if self.engaged and low < min(self.args.z_min, self.args.phone_clear) - 0.006:
            self.disengage(f'the tool or the phone is {low * 1000:.1f} mm above the table')
        if self.session.recording:
            pos, rot = self.tcp_now()
            self.session.add('tcp_target', np.r_[pos, rot.ravel()])
            self.session.add('q_target', self.q_cmd)
            self.session.add('engaged', [float(self.engaged)])
            self.session.add('limited', [float(self.limited)])
            for name, value in src.streams().items():
                self.session.add(name, value)
        self.message = blocked or '; '.join(name for bit, name in LIMIT_NAMES.items() if self.limited & bit)
        if self.limited & 48 and self.why:
            self.message += f' [{self.why}]'
        arm.sleep()

    def _go_home(self) -> None:
        self.disengage()
        sharklog.info('going home')
        self.arm.move_to_joint(np.asarray(self.arm.tool.home, dtype=float), speed=math.radians(15.0))
        self._after_joint_move()

    def _after_joint_move(self) -> None:
        self.q_cmd = self.arm.joint_target().copy()
        if self.cart is not None:
            self.cart.reset()

    # -- the whole run
    def run(self) -> int:
        a, src = self.args, self.source
        log.setup()
        if (
            not 0 < a.max_speed <= 0.25
            or not 0 < a.max_joint_speed <= 90
            or a.z_min < 0.005
            or not 0 < a.max_tilt <= 89
            or not 0 < a.max_heading <= 180
            or a.phone_clear < 0.005
            or a.arm_clear < 0.04
        ):
            print(
                'REFUSED: --max-speed up to 0.25 m/s, --max-joint-speed up to 90 deg/s, --z-min and --phone-clear at least 0.005 m, '
                '--max-tilt up to 89 deg, --max-heading up to 180 deg, --arm-clear at least 0.04 m'
            )
            return 2
        table = a.table_z if a.table_z is not None else 0.0 if a.sim else table_height(Path(a.workspace))
        if table is None:
            print('REFUSED: the table height is not known (run robot/arm_touch_table.py or give --table-z)')
            return 2
        self.table = table
        self.lo, self.hi = load_workspace(Path(a.workspace))
        self.lo[2] = table + a.z_min  # the tool works below the free-space floor on purpose
        cams = (
            ()
            if (a.cams or ('none' if a.sim else 'top,wrist')) == 'none'
            else tuple(c.strip() for c in (a.cams or 'top,wrist').split(','))
        )
        if a.sim:
            sys.path.insert(0, str(ROOT / 'sim'))
            from scene import make_arm

            arm_cm = make_arm(calibration=Path(a.calibration))
        else:
            arm_cm = Arm.from_config('b601_rs', tool=a.tool, calibration=a.calibration, backend='real')

        with arm_cm as arm:
            self.arm = arm
            folded, at_home, roll = start_pose(arm)
            print(
                f'start: q {np.round(np.degrees(arm.q()), 1).tolist()} deg'
                + ('  (motors already enabled: taking the hold over)' if arm.taken_over else '')
            )
            if not (folded or at_home):
                print(
                    "REFUSED: the arm is neither folded nor at the tool's home pose. Bring it there first (robot/arm_move.py) or release it (robot/arm release)."
                )
                return 2
            limits = CartesianLimits.from_dict(arm.tool.cartesian)
            # the tip may go wherever the checks in allowed() let the arm go: the box of the workspace file, not the
            # narrower one of the tool config
            limits.x, limits.y = (0.05, float(self.hi[0])), (float(self.lo[1]), float(self.hi[1]))
            limits.z = (table + a.z_min, min(a.z_max, float(self.hi[2])))
            limits.max_speed, limits.max_ang_speed = a.max_speed, math.radians(a.max_turn)
            limits.max_tilt_deg, limits.max_yaw_deg = a.max_tilt, (None if a.max_heading >= 180 else a.max_heading)
            phone = arm.tool.extra.get('phone') or {}
            if 'body_xyz' in phone:
                placement = arm.model.model.frames[arm.model.tcp_frame_id].placement  # tool frame in link6
                r_l_tcp, p_l_tcp = np.array(placement.rotation), np.array(placement.translation)
                hx, hy = phone['body_half']
                local = np.array([[sx * hx, sy * hy, z] for sx in (-1, 1) for sy in (-1, 1) for z in phone['body_z']])
                in_link6 = (
                    np.asarray(phone['body_xyz'], dtype=float) + local @ np.asarray(phone['body_rot'], dtype=float).T
                )
                self.corners = (in_link6 - p_l_tcp) @ r_l_tcp
            home = np.asarray(arm.tool.home, dtype=float)
            print(
                f"teleoperation by {src.name}; task '{a.task}'"
                + (f' ("{a.instruction}")' if a.instruction else ' (no --instruction given)')
                + f'; table at z = {table * 1000:+.1f} mm'
            )
            print(
                f'  the arm unfolds to home (tip {np.round(arm.model.fk(home)[0], 3).tolist()} m) and waits; it follows only while engaged (space)'
            )
            if src.kind == 'pose':
                print(
                    f'  the tool goes as far as the joints allow; stopped by: the box (tip x up to {limits.x[1]:.2f}, y {limits.y[0]:+.2f}..{limits.y[1]:+.2f}, '
                    f'z up to {limits.z[1]:.2f} m; joint centres and phone inside calibration/workspace.yaml), the table (tip {a.z_min * 1000:g} mm, '
                    f'phone {a.phone_clear * 1000:g} mm above it), the arm itself ({a.arm_clear * 100:g} cm)'
                )
                print(
                    f'  outer bounds: rod within {limits.max_tilt_deg:g} deg of vertical, heading '
                    + ('free' if limits.max_yaw_deg is None else f'within {limits.max_yaw_deg:g} deg of straight ahead')
                    + f'; at most {a.max_speed * 100:g} cm/s and {a.max_turn:g} deg/s'
                )
            else:
                print(
                    f'  joint targets are refused outside the box of calibration/workspace.yaml or lower than {a.z_min * 1000:g} mm above the table; '
                    f'at most {a.max_joint_speed:g} deg/s per joint, 15 deg/s while catching up after engaging'
                )
            for line in src.plan():
                print(f'  {line}')
            print(
                '  recorded per episode: arm log'
                + (f', cameras {", ".join(cams)}' if cams else ', no cameras')
                + f'; at quit: {"home, fold, torque off" if a.end == "fold" else "home, keep holding"}'
            )
            if abs(roll) > math.radians(5.0) and folded and not at_home:
                print(f'  the tool hangs rolled by {math.degrees(roll):+.0f} deg: joint 6 is levelled first, in place')
            if not a.sim and not a.yes:
                print('plan only: nothing moved (add --yes to move the real arm)')
                return 0

            src.open(self)  # before the arm moves: a missing device stops the run here
            try:
                self.session = Session(
                    arm,
                    task=a.task,
                    cams=cams,
                    root=Path(a.root),
                    operator=a.operator,
                    instruction=a.instruction,
                    config_files=(Path(a.tool), Path(a.calibration), Path(a.workspace).with_name('table.yaml')),
                    meta={'teleop': src.name, 'table_z': float(table), 'calibration': str(a.calibration)},
                )
                for w in self.session.pool.warnings() if self.session.pool else []:
                    sharklog.warning(w)
                arm.enable()
                go_home(arm)
                self.q_cmd = arm.joint_target().copy()
                if src.kind == 'pose':
                    self.cart = arm.cartesian(limits)
                sharklog.info(
                    f'ready.  space = engage / disengage   r = record start / stop   f = failed   x = throw the last episode away   h = home   q = quit{src.keys_help}'
                )
                with Keys(a.keys) as keys:
                    t_status, t_ready = -1.0, arm.now()
                    while True:
                        key = keys.get(arm.now() - t_ready)  # a key script counts from "ready"
                        if key == ' ':
                            if self.engaged:
                                self.disengage()
                            else:
                                why = src.engage(self)
                                if why:
                                    sharklog.warning(f'not engaged: {why}')
                                else:
                                    self.engaged, self._approach = True, True
                                    sharklog.info('ENGAGED')
                        elif key == 'r':
                            if self.session.recording:
                                sharklog.info(f'saved {self.session.end(success=True)}')
                            else:
                                sharklog.info(f'recording {self.session.begin()}')
                        elif key == 'f':
                            path = self.session.fail_last()
                            sharklog.warning(f'marked failed: {path}' if path else 'nothing to mark')
                        elif key == 'x':
                            dest = self.session.discard_last()
                            sharklog.warning(f'moved to {dest}' if dest else 'nothing to throw away')
                        elif key == 'h':
                            self._go_home()
                        elif key == 'q':
                            break
                        elif key and not src.key(key, self):
                            pass
                        self._cycle()
                        if arm.now() - t_status > 0.25:
                            t_status = arm.now()
                            tip = arm.tcp_pose()[0]
                            line = (
                                f'{"ENGAGED" if self.engaged else "hold   "} | {self.session.status()} | tip ({tip[0]:.3f}, {tip[1]:+.3f}, {tip[2]:.3f}) '
                                f'| {src.status()} {("| " + self.message) if self.message else ""}'
                            )
                            log.status('  ' + line)
                self.disengage()
                if self.session.recording:
                    sharklog.info(f'saved {self.session.end()}')
                sharklog.info('going home')
                arm.move_to_joint(home, speed=math.radians(15.0))
                if a.end == 'hold':
                    arm.detach()
                else:
                    sharklog.info('folding to the zero pose, then torque off')
            finally:
                src.close()
                if self.session is not None:
                    n = len(self.session.saved)
                    self.session.close()
                    sharklog.info(f'{n} episodes saved in this session')
                log.end_status()
        return 0
