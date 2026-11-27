"""Height of the table (the whiteboard) in the arm's frame, by touching it gently with the tool tip.

    uv run python robot/arm_touch_table.py --yes                  # real arm, in a terminal next to it (about 5 min)
    uv run python robot/arm_touch_table.py                        # real arm: prints the plan, moves nothing
    uv run python robot/arm_touch_table.py --sim --auto           # the whole procedure in the simulated scene
    uv run python robot/arm_touch_table.py --from-data calibration/data/table-*.npz     # recompute, no arm

The operator decides when the tip touches (a rule of this setup: the printed pusher must not be loaded,
so contact is not left to the motors' readings). The program is run by the operator in a terminal:

1. it unfolds to the tool's home pose (tool tip pointing down) and, for every point of --points, moves the tip
   over it at --z-travel and lowers it to --z-start;
2. on Enter the tip descends at --speed (3 mm/s); Enter again stops it, a little above the table;
3. from there the operator lowers it in steps (Enter: 0.5 mm; a number: that many mm, negative lifts) and types
   `t` when the tip touches. The joint angles at that moment are the measurement; the tip goes back up.

The program's own contact detection is only a guard. The tip is told where to go and its real height is measured:
when the table holds it up, it stays above its target. As soon as it is --threshold (3 mm) further above its
target than it was in free air, or a motor torque is --max-torque (1.5 N*m) away from its free-air value, the
descent stops, the target is put back 1 mm above the measured height (which takes the push away) and the operator
is asked whether that was the table. The operator's steps are cut short at the same limit. In the simulation 3 mm
of extra lag is a push of about 2 N.

--auto leaves the decision to that detection (--threshold 4 mm, --max-torque 3 N*m, --speed 5 mm/s): for the
simulator, not for the real arm with the printed pusher.

Results: the joint angles of every touch go to calibration/data/table-<time>.npz, and the heights computed from
them to calibration/table.yaml (in --sim nothing is saved unless --data-dir or --out is given). The heights
depend on the tool model (where the tip is on the flange): after the tool's geometry is updated, --from-data
recomputes them from the saved joint angles without touching anything again. The height reported is that of the
tool's TCP at contact minus --tip-below-tcp, the distance from the TCP to the lowest point of the tool. Accuracy
is limited by the arm's own position error (a few mm): this is the table as the arm sees it, which is what its
Cartesian limits need.

The points must be free whiteboard: no tag, no paper, no object. Before moving, every point is checked for reach
and against the box in calibration/workspace.yaml; the check knows nothing about objects on the table.

Real arm: only with the operator at the motor power switch (docs/en/user/robot-arm-tools.md). Without --yes nothing moves.
A failure, Ctrl-C or a closed terminal leaves the arm holding where it is, with torque on (`robot/arm release`
ends that).
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import select
import signal
import sys
from pathlib import Path

import numpy as np
import yaml
from arm_move import go_home, load_workspace, start_pose, violation
from rebot_control import Arm, ArmConfig, RobotModel, ToolConfig
from rebot_control.cartesian import CartesianLimits
from rebot_control.config import Calibration
from rebot_control.ik import DiffIK

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_POINTS = '0.29,0.11; 0.29,-0.11; 0.34,0.08; 0.34,-0.12; 0.31,0.00'  # free whiteboard on 2026-11-16
TRAVEL_SPEED = 0.05  # m/s between points
APPROACH_SPEED = 0.02  # m/s from the travel height to the start of the slow descent, and back up
STEP_SPEED = 0.002  # m/s for the operator's steps
STEP = 0.0005  # m: one press of Enter
MAX_STEP = 0.005  # m: the largest step the operator can ask for
RELIEF = 0.001  # m: after the guard stopped a descent, the target goes this far above the measured height
FREE_AIR = (0.3, 1.0)  # s after the start of a descent: the window that defines "free air" while moving
FOUND = ('contact', 'operator')  # how a touch that found the table ended
DEFAULTS = {  # speed (m/s), threshold (m), max torque change (N*m)
    'operator': (0.003, 0.003, 1.5),
    'auto': (0.005, 0.004, 3.0),
}


def parse_points(text: str) -> np.ndarray:
    pts = [[float(v) for v in part.split(',')] for part in text.split(';') if part.strip()]
    if not pts or any(len(p) != 2 for p in pts):
        raise ValueError("points are 'x,y; x,y; ...' in metres")
    return np.array(pts)


def go(arm, cart, pos: np.ndarray, rot: np.ndarray, speed: float, timeout: float = 40.0) -> None:
    """Straight line of the tip to ``pos`` at ``speed``, then half a second of standing still."""
    cart.limits.max_speed = speed
    t_end = arm.now() + timeout
    while np.linalg.norm(cart.pos - pos) > 1e-4:
        st = cart.step(pos, rot)
        arm.sleep()
        if not st.ik_ok:
            raise RuntimeError(f'no joint solution on the way to {np.round(pos, 3).tolist()}')
        if arm.now() > t_end:
            raise RuntimeError(f'did not reach {np.round(pos, 3).tolist()} in {timeout:.0f} s')
    for _ in range(int(0.5 / arm.dt)):
        cart.hold()
        arm.sleep()


class Operator:
    """The operator's keyboard: lines typed in the terminal, read without stopping the control loop."""

    def poll(self) -> str | None:
        """A line typed since the last call, or None."""
        if not select.select([sys.stdin], [], [], 0)[0]:
            return None
        line = sys.stdin.readline()
        if line == '':
            raise EOFError('the terminal was closed')
        return line.strip().lower()

    def ask(self, prompt: str, tick) -> str:
        """Print ``prompt`` and call ``tick()`` every control cycle until the operator answers."""
        while self.poll() is not None:  # forget what was typed before the question was on the screen
            pass
        print(prompt, end='', flush=True)
        while True:
            line = self.poll()
            if line is not None:
                return line
            tick()


class Probe:
    """The tool tip over one point: where it is told to be, where it is, and both against their free-air values."""

    def __init__(self, arm, cart, rot: np.ndarray, xy: np.ndarray, args) -> None:
        self.arm, self.cart, self.rot, self.args = arm, cart, rot, args
        self.xy = np.asarray(xy, dtype=float)
        self.data = arm.model.new_data()
        self.t0 = arm.now()
        self.t: list[float] = []
        self.z: list[float] = []  # measured tip height
        self.z_target: list[float] = []  # tip height of the joint target sent to the motors
        self.q: list[np.ndarray] = []
        self.tau: list[np.ndarray] = []
        self.lag0 = float('nan')
        self.tau0 = np.full(arm.n, np.nan)
        self.window = max(3, int(0.05 / arm.dt))
        self.hold(0.3)
        self.reference(0.3)

    def at(self, z: float) -> np.ndarray:
        return np.array([self.xy[0], self.xy[1], z])

    def tick(self, target: np.ndarray | None = None):
        """One control cycle towards ``target`` (None: stand still), and one sample."""
        st = self.cart.hold() if target is None else self.cart.step(target, self.rot)
        self.arm.sleep()
        s = self.arm.state()
        self.t.append(self.arm.now() - self.t0)
        self.q.append(s.q)
        self.tau.append(s.tau)
        self.z.append(self.arm.model.fk(s.q, self.data)[0][2])
        self.z_target.append(self.arm.model.fk(self.arm.filter.q_filt, self.data)[0][2])
        return st

    def hold(self, seconds: float) -> None:
        for _ in range(max(1, int(seconds / self.arm.dt))):
            self.tick()

    def _last(self, seconds: float) -> slice:
        return slice(-max(self.window, int(seconds / self.arm.dt)), None)

    def reference(self, seconds: float) -> None:
        """Take the last ``seconds`` as free air."""
        sl = self._last(seconds)
        self.lag0 = float(np.median(np.array(self.z[sl]) - np.array(self.z_target[sl])))
        self.tau0 = np.median(np.array(self.tau[sl]), axis=0)

    def extra_lag(self) -> float:
        """How much further above its target the tip is than in free air (m)."""
        sl = slice(-self.window, None)
        return float(np.mean(np.array(self.z[sl]) - np.array(self.z_target[sl]))) - self.lag0

    def resisted(self) -> str | None:
        if self.extra_lag() > self.args.threshold:
            return 'lag'
        if np.abs(self.tau[-1] - self.tau0).max() > self.args.max_torque:
            return 'torque'
        return None

    def descend(self, operator: Operator | None = None) -> str:
        """Go down at --speed until something ends it: 'lag', 'torque', 'key', 'bottom' or 'no joint solution'."""
        args, bottom = self.args, self.at(self.args.z_min)
        self.cart.limits.max_speed = args.speed
        start, referenced = self.arm.now(), False
        while True:
            st = self.tick(bottom)
            moving = self.arm.now() - start
            if not referenced and moving > FREE_AIR[1]:
                self.reference(FREE_AIR[1] - FREE_AIR[0])  # from here on, free air is the tip in motion
                referenced = True
            if not st.ik_ok:
                return 'no joint solution'
            if operator is not None:
                if operator.poll() is not None:
                    return 'key'
                if len(self.t) % max(1, int(0.1 / self.arm.dt)) == 0:
                    print(f'\r  下降中：推杆尖高度 {self.z[-1] * 1000:+6.1f} mm（回车 = 停下）', end='', flush=True)
            why = self.resisted()
            if why:
                return why
            if self.cart.pos[2] <= args.z_min + 1e-5:
                return 'bottom'

    def move_to(self, z: float, speed: float, settle: float = 0.4) -> None:
        """Put the target at height ``z`` and wait until the motors have been told to be there."""
        self.cart.limits.max_speed = speed
        target = self.at(z)
        while abs(self.cart.pos[2] - z) > 1e-5:
            if not self.tick(target).ik_ok:
                raise RuntimeError(f'no joint solution at z = {z:.3f}')
        self.hold(settle)

    def result(self, reason: str, seconds: float = 0.15) -> dict:
        """What the last ``seconds`` say: the joint angles of the touch, if ``reason`` is one."""
        sl = self._last(seconds)
        out = {
            'reason': reason,
            'xy': self.xy,
            'q': np.median(np.array(self.q[sl]), axis=0),
            'z_scatter': float(np.std(np.array(self.z[sl]))),
            'lag_free': self.lag0,
            'extra_lag': self.extra_lag(),
            'tau_change': np.array(self.tau[sl]).mean(0) - self.tau0,
        }
        if self.arm.is_sim:  # the simulator knows the force on the rod
            out['force'] = _sim_rod_force(self.arm)
        return out

    def finish(self, out: dict) -> dict:
        out['trace'] = np.column_stack([self.t, self.z, self.z_target])
        go(self.arm, self.cart, self.at(self.args.z_start), self.rot, APPROACH_SPEED)
        return out


def touch_auto(probe: Probe) -> dict:
    """One descent that ends when the program's own detection says so."""
    why = probe.descend()
    reason = {'lag': 'contact', 'torque': 'torque limit', 'bottom': 'nothing found'}.get(why, why)
    return probe.finish(probe.result(reason))


def touch_operator(probe: Probe, operator: Operator, label: str) -> dict:
    """One touch decided by the operator. Returns with reason 'operator', 'skipped', 'quit' or 'nothing found'."""
    args = probe.args
    mm = lambda v: f'{v * 1000:+.1f} mm'

    def leave(key: str) -> dict:
        return probe.finish(probe.result('quit' if key == 'q' else 'skipped'))

    def relieve(why: str) -> dict | None:
        """The guard stopped the descent: take the push away and ask. Returns the touch, or None to go on."""
        pressed = probe.result('operator')
        probe.move_to(min(probe.z[-1] + RELIEF, args.z_start), STEP_SPEED)  # target back to just above where the tip is
        what = f'推杆尖比目标高出 {pressed["extra_lag"] * 1000:.1f} mm' if why == 'lag' else '电机力矩变化超过限值'
        ans = operator.ask(
            f'\n  遇到阻力（{what}），已停止并卸力，推杆尖高度 {mm(probe.z[-1])}。\n'
            '  推杆尖碰到桌面了吗？ y = 碰到了，记录 | n = 没有，继续 > ',
            probe.tick,
        )
        if ans == 'y':
            return pressed
        probe.reference(0.3)  # what it feels now is free air
        return None

    key = operator.ask(
        f'{label}：推杆尖在上方 {mm(probe.z[-1])}。回车 = 以 {args.speed * 1000:g} mm/s 下降，快碰到时再按回车停下'
        ' | s = 跳过 | q = 结束 > ',
        probe.tick,
    )
    if key in ('s', 'q'):
        return leave(key)
    descending = True
    while True:
        if descending:
            why = probe.descend(operator)
            descending = False
            if why == 'key':
                probe.hold(0.3)
                print(f'\r  已停下，推杆尖高度 {mm(probe.z[-1])}' + ' ' * 30)
            elif why in ('lag', 'torque'):
                out = relieve(why)
                if out:
                    return probe.finish(out)
            else:
                print(
                    f'\n  {"降到最低高度 " + mm(args.z_min) + " 仍没有碰到" if why == "bottom" else "到不了更低的位置"}，这个点放弃'
                )
                return probe.finish(probe.result('nothing found'))
        key = operator.ask(
            '  回车 = 再降 0.5 mm | 数字 = 下降的毫米数（负数抬起）| c = 继续慢速下降 | t = 已接触，记录 | s = 跳过 | q = 结束 > ',
            probe.tick,
        )
        if key in ('s', 'q'):
            return leave(key)
        if key == 't':
            probe.hold(0.3)
            out = probe.result('operator', seconds=0.3)
            print(f'  已记录：推杆尖高度 {mm(probe.z[-1])}')
            return probe.finish(out)
        if key == 'c':
            descending = True
            continue
        try:
            step = STEP if key == '' else float(key) / 1000.0
        except ValueError:
            print('  没看懂，请重新输入')
            continue
        step = float(np.clip(step, -MAX_STEP, MAX_STEP))
        if step > 0:  # never ask for more push than the guard allows
            room = args.threshold - probe.extra_lag()
            if room < 1e-4:
                out = relieve('lag')
                if out:
                    return probe.finish(out)
                continue
            step = min(step, room)
        z_before = probe.z[-1]
        probe.move_to(float(np.clip(probe.cart.pos[2] - step, args.z_min, args.z_start)), STEP_SPEED)
        print(
            f'  目标下降 {step * 1000:.1f} mm，实际下降 {round((z_before - probe.z[-1]) * 1000, 1) + 0.0:.1f} mm；推杆尖高度 {mm(probe.z[-1])}，'
            f'比目标高出 {max(probe.extra_lag(), 0.0) * 1000:.1f} mm'
        )
        why = probe.resisted() if step > 0 else None
        if why:
            out = relieve(why)
            if out:
                return probe.finish(out)


def _sim_rod_force(arm) -> float:
    import mujoco

    m, d = arm.backend.mj_model, arm.backend.mj_data
    rod = mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, 'rod')
    total, f = 0.0, np.zeros(6)
    for i in range(d.ncon):
        if rod in (d.contact[i].geom1, d.contact[i].geom2):
            mujoco.mj_contactForce(m, d, i, f)
            total += float(f[0])
    return total


def lowest_point(model: RobotModel, q: np.ndarray, tip_below_tcp: float, data=None) -> np.ndarray:
    """The tool's lowest point at joint angles ``q``: where it touches a level table.

    A tool config with ``tip: {radius: r}`` has a ball tip centred ``r`` behind the TCP on the tool z axis; its
    lowest point is ``r`` under that centre whatever the lean of the rod. Otherwise it is the TCP itself.
    ``tip_below_tcp`` lowers the result further.
    """
    p, rot = model.fk(q, data)
    r = float((model.tool.extra.get('tip') or {}).get('radius', 0.0))
    low = p - r * rot[:, 2]
    low[2] -= r + tip_below_tcp
    return low


def heights(model: RobotModel, q: np.ndarray, tip_below_tcp: float) -> np.ndarray:
    """Lowest points of the tool (N, 3) at the joint angles of the touches."""
    data = model.new_data()
    return np.array([lowest_point(model, qi, tip_below_tcp, data) for qi in q])


def report(p: np.ndarray, label: str = '') -> dict:
    """Print the touched points and the plane through them; returns what goes into the result file."""
    z = p[:, 2]
    res = {
        'z': round(float(z.mean()), 4),
        'z_min': round(float(z.min()), 4),
        'z_max': round(float(z.max()), 4),
        'points': np.round(p, 4).tolist(),
    }
    print(
        f'table height{label}: mean {z.mean() * 1000:+.1f} mm, from {z.min() * 1000:+.1f} to {z.max() * 1000:+.1f} mm over {len(z)} touches'
    )
    xy = np.unique(np.round(p[:, :2], 2), axis=0)
    if len(xy) >= 3 and np.linalg.matrix_rank(np.c_[xy, np.ones(len(xy))]) == 3:
        coef, *_ = np.linalg.lstsq(np.c_[np.ones(len(p)), p[:, :2]], z, rcond=None)
        resid = z - np.c_[np.ones(len(p)), p[:, :2]] @ coef
        res['plane'] = {
            'z0': round(float(coef[0]), 4),
            'dz_dx': round(float(coef[1]), 4),
            'dz_dy': round(float(coef[2]), 4),
            'residual_rms': round(float(np.sqrt((resid**2).mean())), 4),
        }
        print(
            f'  plane z = {coef[0] * 1000:+.1f} mm {coef[1] * 100:+.2f} mm per 10 cm of x {coef[2] * 100:+.2f} mm per 10 cm of y; '
            f'touches differ from it by {np.sqrt((resid**2).mean()) * 1000:.1f} mm rms'
        )
    return res


def write_result(path: Path, res: dict, tool: str, tip_below_tcp: float, data_file: str, calibration: str) -> None:
    header = f"""# Written by robot/arm_touch_table.py on {dt.date.today().isoformat()}: do not edit, run the tool again
# (--from-data recomputes it from the saved joint angles, e.g. after the tool model changed).
# Height of the table (whiteboard surface) in the arm's base frame, metres, as the arm itself measures it by
# touching: z is the mean over the touches, points are the touched positions, plane is fitted through them.
"""
    out = {'table': res, 'tool': tool, 'tip_below_tcp': tip_below_tcp, 'calibration': calibration, 'data': data_file}
    path.write_text(header + yaml.safe_dump(out, sort_keys=False, default_flow_style=None, width=200))
    print(f'wrote {path}')


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--points', default=DEFAULT_POINTS, help="'x,y; x,y; ...' (m, arm frame): free spots on the table")
    ap.add_argument('--auto', action='store_true', help='let the program decide when the tip touches (simulator)')
    ap.add_argument('--repeat', type=int, help='touches per point (default: 1 with the operator, 2 with --auto)')
    ap.add_argument('--z-travel', type=float, default=0.08, help='tip height when moving between points (m)')
    ap.add_argument('--z-start', type=float, default=0.05, help='tip height where the slow descent starts (m)')
    ap.add_argument('--z-min', type=float, default=-0.03, help='lowest tip target (m): the descent gives up there')
    ap.add_argument('--speed', type=float, help='descent speed (m/s), at most 0.01 (default 0.003, --auto 0.005)')
    ap.add_argument(
        '--threshold', type=float, help='extra lag of the tip that stops a descent (m; default 0.003, --auto 0.004)'
    )
    ap.add_argument(
        '--max-torque', type=float, help='change of any motor torque that stops a descent (N*m; default 1.5, --auto 3)'
    )
    ap.add_argument(
        '--tip-below-tcp', type=float, default=0.0, help="distance from the TCP down to the tool's lowest point (m)"
    )
    ap.add_argument(
        '--end', choices=('fold', 'hold'), default='fold', help='fold and torque off, or keep holding at home'
    )
    ap.add_argument('--sim', action='store_true')
    ap.add_argument('--sim-start', help="simulator: joint angles at start, 'deg,deg,...' (default: folded)")
    ap.add_argument('--yes', action='store_true', help='real arm: actually move (default: print the plan only)')
    ap.add_argument('--tool', default=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'))
    ap.add_argument('--calibration', default=str(ROOT / 'calibration' / 'b601_rs.yaml'))
    ap.add_argument('--workspace', default=str(ROOT / 'calibration' / 'workspace.yaml'))
    ap.add_argument('--out', help='result file (default calibration/table.yaml; with --sim: none)')
    ap.add_argument('--data-dir', help='where the touches are saved (default calibration/data; with --sim: nowhere)')
    ap.add_argument('--from-data', help='recompute the heights from a saved .npz with the current tool model; no arm')
    ap.add_argument('--no-save', action='store_true')
    args = ap.parse_args()
    speed, threshold, max_torque = DEFAULTS['auto' if args.auto else 'operator']
    args.speed = speed if args.speed is None else args.speed
    args.threshold = threshold if args.threshold is None else args.threshold
    args.max_torque = max_torque if args.max_torque is None else args.max_torque
    args.repeat = (2 if args.auto else 1) if args.repeat is None else args.repeat
    if not args.sim:
        args.out = args.out or str(ROOT / 'calibration' / 'table.yaml')
        args.data_dir = args.data_dir or str(ROOT / 'calibration' / 'data')
    if not 0 < args.speed <= 0.01:
        ap.error('--speed must be between 0 and 0.01 m/s')
    if not args.z_min < args.z_start <= args.z_travel:
        ap.error('need --z-min < --z-start <= --z-travel')

    if args.from_data:
        d = np.load(args.from_data, allow_pickle=False)
        cal = Calibration.load(args.calibration) if Path(args.calibration).is_file() else None
        model = RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(args.tool), cal)
        found = d['found'].astype(bool)
        res = report(heights(model, d['q'][found], args.tip_below_tcp), f' (tool {args.tool})')
        if not args.no_save and args.out:
            write_result(Path(args.out), res, args.tool, args.tip_below_tcp, args.from_data, args.calibration)
        return 0

    def _terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _terminate)

    points = parse_points(args.points)
    lo, hi = load_workspace(Path(args.workspace))
    lo[2] = -1.0  # the floor is this tool's business: --z-min
    if args.sim:
        sys.path.insert(0, str(ROOT / 'sim'))
        from scene import make_arm

        q0 = {'q0': np.radians([float(v) for v in args.sim_start.split(',')])} if args.sim_start else {}
        arm_cm = make_arm(calibration=Path(args.calibration), **q0)
    else:
        arm_cm = Arm.from_config('b601_rs', tool=args.tool, calibration=args.calibration, backend='real')

    touches: list[dict] = []
    with arm_cm as arm:
        home = np.asarray(arm.tool.home, dtype=float)
        p_home, rot = arm.model.fk(home)
        start = arm.q()
        folded, at_home, roll = start_pose(arm)
        print(
            f'start: q {np.round(np.degrees(start), 1).tolist()} deg'
            + ('  (motors already enabled: taking the hold over)' if arm.taken_over else '')
        )
        if not (folded or at_home):
            print(
                "REFUSED: the arm is neither folded nor at the tool's home pose. Bring it there first (robot/arm_move.py) "
                'or release it (robot/arm release).'
            )
            return 2
        hangs = folded and not at_home and abs(roll) > math.radians(5.0)
        if hangs:
            print(f'the tool hangs rolled by {math.degrees(roll):+.0f} deg: joint 6 is levelled first, in place')

        # ---- plan and check ----
        limits = CartesianLimits(
            x=(lo[0], hi[0]),
            y=(lo[1], hi[1]),
            z=(args.z_min, max(args.z_travel, p_home[2]) + 0.02),
            max_speed=TRAVEL_SPEED,
            max_ang_speed=0.5,
        )
        ik, problems = DiffIK(arm.model, posture=home), []
        for k, xy in enumerate(points, 1):
            for z in (args.z_travel, args.z_min):
                r = ik.solve(np.array([xy[0], xy[1], z]), rot, home, max_iters=200)
                why = None if r.success else 'out of reach'
                why = why or violation(arm.model, r.q, lo, hi)
                if why:
                    problems.append(f'point {k} ({xy[0]:.2f}, {xy[1]:.2f}) at z = {z:.2f}: {why}')
                    break
        print(f'{len(points)} points x {args.repeat} touches: {np.round(points, 2).tolist()}')
        print(
            f'contact decided by {"the program" if args.auto else "the operator"}; travel at z = {args.z_travel:.2f} m, slow descent from '
            f'{args.z_start:.2f} m at {args.speed * 1000:g} mm/s, give up at {args.z_min:.2f} m; a descent stops by itself at '
            f'{args.threshold * 1000:g} mm of extra lag or {args.max_torque:g} N*m of torque change; '
            f'then: {"fold, torque off" if args.end == "fold" else "keep holding at home, enabled"}'
        )
        if problems:
            print('REFUSED:\n  ' + '\n  '.join(problems))
            return 2
        if not args.sim and not args.yes:
            print('plan only: nothing moved (add --yes to move the real arm)')
            return 0
        operator = None
        if not args.auto:
            if not sys.stdin.isatty():
                print(
                    'REFUSED: the operator decides when the tip touches, so this must run in a terminal (or with --auto in the simulator)'
                )
                return 2
            operator = Operator()
            first = '上力矩，' + ('先原地把第 6 轴转平，再' if hangs else '') + '展开到 home 位，然后移到第 1 个点上方'
            if operator.ask(f'回车 = {first} | q = 不做了 > ', arm.sleep) == 'q':
                return 0

        # ---- move ----
        arm.enable()
        go_home(arm)
        cart = arm.cartesian(limits)
        quit_ = False
        for k, xy in enumerate(points, 1):
            go(arm, cart, np.array([xy[0], xy[1], args.z_travel]), rot, TRAVEL_SPEED)
            go(arm, cart, np.array([xy[0], xy[1], args.z_start]), rot, APPROACH_SPEED)
            for i in range(args.repeat):
                probe = Probe(arm, cart, rot, xy, args)
                label = f'点 {k}/{len(points)} ({xy[0]:.2f}, {xy[1]:.2f})' + (
                    f' 第 {i + 1} 次' if args.repeat > 1 else ''
                )
                r = touch_auto(probe) if args.auto else touch_operator(probe, operator, label)
                touches.append(r)
                z = lowest_point(arm.model, r['q'], args.tip_below_tcp)[2]
                force = f' | force {r["force"]:.1f} N' if 'force' in r else ''
                print(
                    f'point {k} ({xy[0]:.2f}, {xy[1]:.2f}): {r["reason"]:13s} z = {z * 1000:+6.1f} mm (scatter {r["z_scatter"] * 1000:.2f}) | '
                    f'lag in free air {r["lag_free"] * 1000:+.1f} mm, extra {r["extra_lag"] * 1000:+.1f} mm | torque change '
                    f'{np.round(r["tau_change"], 2).tolist()} N*m | temp max {arm.state().temp.max():.0f} C{force}',
                    flush=True,
                )
                quit_ = r['reason'] == 'quit'
                if quit_ or r['reason'] == 'skipped':
                    break
            go(arm, cart, np.array([xy[0], xy[1], args.z_travel]), rot, APPROACH_SPEED)
            if quit_:
                break
        go(arm, cart, np.array([p_home[0], p_home[1], max(p_home[2], args.z_travel)]), rot, TRAVEL_SPEED)
        arm.move_to_joint(home, speed=math.radians(15.0))
        if args.end == 'hold':
            arm.detach()
            print('holding the home pose with torque ON; end it with `robot/arm release`', flush=True)
        else:
            print('folding to the zero pose, then torque off', flush=True)  # done by the normal exit below

    # ---- result ----
    if not touches:
        return 0
    found = np.array([r['reason'] in FOUND for r in touches])
    q = np.array([r['q'] for r in touches])
    data_file = ''
    if not args.no_save and args.data_dir:
        path = Path(args.data_dir).resolve() / f'table-{dt.datetime.now():%Y%m%d-%H%M%S}.npz'
        np.savez(
            path,
            q=q,
            found=found,
            xy=np.array([r['xy'] for r in touches]),
            reason=np.array([r['reason'] for r in touches]),
            threshold=args.threshold,
            speed=args.speed,
            **{f'trace_{i}': r['trace'] for i, r in enumerate(touches)},
        )
        data_file = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
        print(f'joint angles and traces of the touches: {path}')
    if not found.any():
        print('no touch found the table: nothing to report')
        return 1
    if not found.all():
        print(f'{(~found).sum()} of {len(found)} descents did not end in contact; they are left out')
    cal = Calibration.load(args.calibration) if Path(args.calibration).is_file() else None
    res = report(
        heights(RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(args.tool), cal), q[found], args.tip_below_tcp)
    )
    if not args.no_save and args.out:
        write_result(Path(args.out), res, args.tool, args.tip_below_tcp, data_file, str(Path(args.calibration)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
