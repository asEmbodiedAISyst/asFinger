"""Teleoperate the arm with a Star Arm 102 leader arm, joint to joint, and record episodes while doing it.

    uv run python robot/teleop_star.py --check            # read the leader and the arm side by side; nothing moves
    uv run python robot/teleop_star.py                    # real arm: plan only, nothing moves
    uv run python robot/teleop_star.py --yes              # real arm
    uv run python robot/teleop_star.py --set-zero         # write the leader's zero into its servos (see below)
    uv run python robot/teleop_star.py --sim --fake --keys "1:space,3:r,12:r,13:q"    # simulator, scripted leader

The leader is read the way the official reBot / LeRobot support reads it (lerobot-teleoperator-rebot-arm-102,
LeRobot's rebot_102_leader): Fashion Star bus servos with ids 0-5 for joints 1-6 on a USB serial adapter at
1 Mbit/s, through the `motorbridge-smart-servo` package; angles in degrees, multi-turn counter reset at connect,
each reading brought into the 360 deg window around the joint's range. The mapping is joint to joint:

    follower joint angle = sign x leader angle + offset        signs (+1, +1, -1, -1, -1, +1), offsets 0

which is the official mapping onto the RS motors (the gripper handle, id 6, is not used: this arm has none).
Port, ids, signs and offsets are in calibration/star_leader.yaml.

Zero: the official procedure puts the leader in its zero pose - folded like the follower's folded pose - and writes
that as the origin into the servos (`--set-zero`, asks for confirmation; it changes the servos permanently).
`--check` shows whether the zeros and signs agree before anything moves: with the arm folded and the leader
folded all six lines should read about zero, and moving one leader joint should move the mapped value the way
that follower joint counts.

Teleoperating: the arm unfolds to its home pose and waits. Pose the leader like the arm, then press space: the arm
only engages when every leader joint is within --max-engage-diff of the arm's, catches up at 15 deg/s and then
follows. It disengages by itself when the leader stops answering.

Keys: see robot/teleop.py. Recorded in every episode in addition: `leader_raw` (deg, as read) and `leader_target`
(rad, mapped to the follower's joints).

Linux: the adapter shows up as /dev/ttyUSB*; the user needs the right to open it (group `dialout`), and the
`brltty` package grabs CH340 adapters and has to be removed if the port does not appear.
"""

from __future__ import annotations

import argparse
import math
import sys
import threading
import time
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from episode import ROOT  # noqa: E402
from teleop import Source, Teleop, add_arguments  # noqa: E402

CONFIG = ROOT / 'calibration' / 'star_leader.yaml'
MAX_AGE = 0.2  # s: older readings are not followed


class StarLeader:
    """The leader arm: a thread keeps the latest joint angles."""

    def __init__(self, cfg: dict) -> None:
        from motorbridge_smart_servo import FashionStarServo

        self.ids = [int(i) for i in cfg['ids']]
        self.signs = np.asarray(cfg['signs'], dtype=float)
        self.offsets = np.asarray(cfg['offsets_deg'], dtype=float)
        self.ranges = np.asarray(cfg['ranges_deg'], dtype=float)
        self.bus = FashionStarServo(cfg['port'], baudrate=int(cfg['baudrate']))
        missing = [i for i in self.ids if not self.bus.ping(i)]
        if missing:
            self.bus.close()
            raise RuntimeError(f'leader servos {missing} do not answer on {cfg["port"]} (power? the right port?)')
        for i in self.ids:
            self.bus.unlock(i)  # free to move by hand (matters on the motorised leader variant)
            time.sleep(0.01)
            self.bus.reset_multi_turn(i)
        self._lock = threading.Lock()
        self._latest: tuple[float, np.ndarray] | None = None
        self.errors = 0
        self.rate = 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name='star-leader', daemon=True)
        self._thread.start()

    def _read_once(self) -> np.ndarray | None:
        result = self.bus.sync_monitor(self.ids)
        raw = np.empty(len(self.ids))
        for k, i in enumerate(self.ids):
            m = result.get(i)
            if m is None:
                return None
            lo, hi = self.ranges[k]
            center = 0.5 * (lo + hi)
            raw[k] = m.angle_deg - round((m.angle_deg - center) / 360.0) * 360.0  # into the window around the range
        return raw

    def _run(self) -> None:
        n, t0 = 0, time.monotonic()
        while not self._stop.is_set():
            try:
                raw = self._read_once()
            except Exception:  # noqa: BLE001 - a bus error: count it, the age of the last reading tells the rest
                raw = None
            if raw is None:
                self.errors += 1
                time.sleep(0.005)
            else:
                with self._lock:
                    self._latest = (time.monotonic(), raw)
                n += 1
            if time.monotonic() - t0 > 1.0:
                self.rate, n, t0 = n / (time.monotonic() - t0), 0, time.monotonic()
            time.sleep(0.002)

    def latest(self) -> tuple[float, np.ndarray] | None:
        """(age in seconds, raw angles in deg) or None before the first reading."""
        with self._lock:
            if self._latest is None:
                return None
            t, raw = self._latest
        return time.monotonic() - t, raw.copy()

    def to_follower(self, raw: np.ndarray) -> np.ndarray:
        """Follower joint angles (rad) for leader angles (deg)."""
        return np.radians(self.signs * np.clip(raw, self.ranges[:, 0], self.ranges[:, 1]) + self.offsets)

    def set_zero(self) -> None:
        for i in self.ids:
            self.bus.unlock(i)
            time.sleep(0.01)
            self.bus.set_origin_point(i)
            time.sleep(0.01)
            self.bus.reset_multi_turn(i)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        self.bus.close()


class ScriptedLeader:
    """A leader that starts where the follower is and wanders a little: for the simulator and the tests."""

    def __init__(self, clock, q_follower: np.ndarray, cfg: dict) -> None:
        self.clock, self.t0 = clock, clock()
        self.signs, self.offsets = np.asarray(cfg['signs'], dtype=float), np.asarray(cfg['offsets_deg'], dtype=float)
        self.ranges = np.asarray(cfg['ranges_deg'], dtype=float)
        self.raw0 = (np.degrees(q_follower) - self.offsets) / self.signs
        self.errors, self.rate = 0, 30.0

    def latest(self):
        t = self.clock() - self.t0
        w = 2 * math.pi / 8.0
        d = np.array(
            [
                12 * math.sin(w * t),
                8 * math.sin(w * t),
                -8 * (1 - math.cos(w * t)),
                5 * math.sin(2 * w * t),
                0.0,
                10 * math.sin(w * t),
            ]
        )
        return 0.0, self.raw0 + d / self.signs

    to_follower = StarLeader.to_follower

    def close(self) -> None:
        pass


class StarSource(Source):
    name = 'Star Arm 102 leader'
    kind = 'joints'

    def __init__(self, args: argparse.Namespace, cfg: dict) -> None:
        self.args, self.cfg = args, cfg
        self.leader = None
        self.raw = np.zeros(6)
        self.q_des = np.zeros(6)
        self.diff = np.zeros(6)

    def plan(self) -> list[str]:
        c = self.cfg
        return [
            f'leader: {"scripted (simulator)" if self.args.fake else c["port"]}, servo ids {c["ids"]}, follower = sign x leader + offset with signs {c["signs"]}, '
            f'offsets {c["offsets_deg"]} deg',
            f"engages only when every leader joint is within {self.args.max_engage_diff:g} deg of the arm's; then catches up at 15 deg/s and follows",
        ]

    def open(self, app: Teleop) -> None:
        if self.args.fake:
            self.leader = ScriptedLeader(app.arm.now, np.asarray(app.arm.tool.home, dtype=float), self.cfg)
        else:
            self.leader = StarLeader(self.cfg)

    def close(self) -> None:
        if self.leader is not None:
            self.leader.close()

    def _read(self, app: Teleop) -> str | None:
        got = self.leader.latest()
        if got is None:
            return 'no reading from the leader yet'
        age, self.raw = got
        if age > MAX_AGE:
            return f'the leader has not answered for {age:.2f} s'
        self.q_des = self.leader.to_follower(self.raw)
        if app.q_cmd is not None:
            self.diff = np.degrees(self.q_des - app.q_cmd)
        return None

    def engage(self, app: Teleop) -> str | None:
        why = self._read(app)
        if why:
            return why
        if np.abs(self.diff).max() > self.args.max_engage_diff:
            return (
                f'the leader is not posed like the arm: differences {np.round(self.diff, 0).astype(int).tolist()} deg '
                f'(limit {self.args.max_engage_diff:g}); move the leader until they are small'
            )
        return None

    def target(self, app: Teleop):
        why = self._read(app)
        return why if why else self.q_des

    def streams(self) -> dict[str, np.ndarray]:
        return {'leader_raw': self.raw, 'leader_target': self.q_des}

    def status(self) -> str:
        return (
            f'leader - arm {np.round(self.diff, 0).astype(int).tolist()} deg, {self.leader.rate:.0f} Hz'
            if self.leader is not None
            else ''
        )

    def idle(self, app: Teleop) -> None:
        self._read(app)


def load_config(path: Path) -> dict:
    cfg = yaml.safe_load(path.read_text())
    for key in ('ids', 'signs', 'offsets_deg', 'ranges_deg'):
        if len(cfg[key]) != 6:
            raise ValueError(f'{path}: `{key}` needs 6 entries')
    if any(abs(s) != 1 for s in cfg['signs']):
        raise ValueError(f'{path}: signs are +1 or -1')
    return cfg


def check(cfg: dict, args: argparse.Namespace) -> int:
    """Leader and arm side by side, read only."""
    from rebot_control import Arm

    leader = StarLeader(cfg)
    try:
        with Arm.from_config('b601_rs', tool=args.tool, calibration=args.calibration, backend='real') as arm:
            print('leader and arm, read only (nothing moves). Ctrl-C to stop.')
            print(
                'with both folded every line should be near zero; move one leader joint and watch the sign of `mapped`'
            )
            names = arm.cfg.joints
            t_end = time.monotonic() + args.seconds
            first = True
            while time.monotonic() < t_end:
                got = leader.latest()
                q = np.degrees(arm.q())
                if got is not None:
                    age, raw = got
                    mapped = np.degrees(leader.to_follower(raw))
                    if not first:
                        print(f'\x1b[{len(names) + 1}A', end='')
                    first = False
                    print(
                        f'{"joint":8s} {"leader raw":>11s} {"mapped":>9s} {"arm":>9s} {"mapped-arm":>11s}   ({leader.rate:.0f} Hz, age {age * 1000:.0f} ms, {leader.errors} read errors)   '
                    )
                    for k, name in enumerate(names):
                        print(f'{name:8s} {raw[k]:+11.1f} {mapped[k]:+9.1f} {q[k]:+9.1f} {mapped[k] - q[k]:+11.1f}   ')
                arm.sleep(0.2)
    except KeyboardInterrupt:
        pass
    finally:
        leader.close()
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--leader', default=str(CONFIG), help='leader configuration file')
    ap.add_argument('--port', help='serial port of the leader, overriding the file')
    ap.add_argument('--check', action='store_true', help='show leader and arm angles side by side; nothing moves')
    ap.add_argument('--seconds', type=float, default=600.0, help='how long --check runs')
    ap.add_argument(
        '--set-zero', action='store_true', help="write the leader's present pose into its servos as the zero"
    )
    ap.add_argument(
        '--max-engage-diff',
        type=float,
        default=15.0,
        help='largest leader - arm difference at which engaging is allowed (deg)',
    )
    ap.add_argument('--fake', action='store_true', help='simulator: a scripted leader instead of the real one')
    add_arguments(ap)
    args = ap.parse_args()
    cfg = load_config(Path(args.leader))
    if args.port:
        cfg['port'] = args.port
    if args.fake and not args.sim:
        print('REFUSED: --fake is for the simulator')
        return 2
    if args.set_zero:
        print(
            f"This writes the leader's PRESENT pose into its six servos ({cfg['port']}, ids {cfg['ids']}) as their zero, permanently."
        )
        print("Fold the leader into its zero pose first: the pose that corresponds to the arm's folded pose.")
        if input('Type `zero` to do it: ').strip() != 'zero':
            print('nothing changed')
            return 1
        leader = StarLeader(cfg)
        try:
            leader.set_zero()
            time.sleep(0.3)
            print('done; the leader now reads', np.round(leader.latest()[1], 1).tolist(), 'deg')
        finally:
            leader.close()
        return 0
    if args.check:
        return check(cfg, args)
    return Teleop(StarSource(args, cfg), args).run()


if __name__ == '__main__':
    sys.exit(main())
