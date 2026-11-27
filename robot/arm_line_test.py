"""Cartesian straight-line test over the whiteboard, recorded as an episode (arm log + both phones).

    uv run python robot/arm_line_test.py                 # real arm: print the plan only, nothing moves
    uv run python robot/arm_line_test.py --yes           # real arm: run it
    uv run python robot/arm_line_test.py --sim           # simulator (no cameras, nothing saved unless --save)
    uv run python robot/arm_line_test.py --from-data data/episodes/<name>    # recompute the report

What it does: from the folded pose (or home) it goes to the tool's home pose, then moves the pusher tip along
straight lines with the Cartesian controller, the rod vertical and the tool's orientation fixed:

- a pattern of lines along x and y at `--high` above the table, once per speed in `--speeds`;
- straight down to `--low` above the table (pushing height), one line along x there and back at each of
  `--low-speeds`, and straight up again.

Then home, fold, torque off (`--end hold` keeps holding at home). Nothing is meant to be touched: the lines must
be over free table, and heights are those of the tool's lowest point above the table of calibration/table.yaml
(in the simulator the table is at z = 0).

Reported for every line, from the joint angles the motors measured: how far the tip left the ideal line sideways
and in height, how far it ran behind the command, the lean of the rod, and the error after stopping. This is the
arm's own view (encoders and model); it says nothing about where the tip is in the room.

Safety: the plan is checked first (reach, box, floor). While moving, the test aborts - stops, lifts the tip
straight up, goes home and folds - if the tip is lower than `--min-clear` above the table or further than 1.5 cm
from where the motors were told to be. The library's own stops (stall, temperature) leave the arm holding where it is.
"""

from __future__ import annotations

import argparse
import math
import os
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arm_move import go_home, load_workspace, start_pose, table_height, violation  # noqa: E402
from arm_touch_table import lowest_point  # noqa: E402
from episode import DATA, EpisodeRecorder, describe, load  # noqa: E402
from rebot_control import Arm, ArmConfig, RobotModel, ToolConfig  # noqa: E402
from rebot_control.config import Calibration, RippleParams  # noqa: E402
from rebot_control.cartesian import CartesianLimits  # noqa: E402
from rebot_control.ik import DiffIK  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DOWN = np.array([[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]])  # rod straight down, tool x forward
SETTLE = 0.6  # s held at the end of every line
VERTICAL_SPEED = 0.03  # m/s, at most, on the lines going down and up
MAX_SPEED = 0.15  # m/s: no line is run faster


class Abort(Exception):
    pass


def plan(
    x: tuple[float, float],
    y: float,
    z_high: float,
    z_low: float,
    low_y: float,
    speeds: list[float],
    low_speeds: list[float],
) -> list[dict]:
    """The lines to run: name, start, end (tip positions, arm frame, m) and speed (m/s)."""
    x0, x1 = x
    P = lambda px, py, pz: np.array([px, py, pz])  # noqa: E731
    out = []
    for v in speeds:
        tag = f'high {v * 100:g} cm/s'
        corners = [
            ('x+', (x0, 0), (x1, 0)),
            ('y+', (x1, 0), (x1, y)),
            ('x-', (x1, y), (x0, y)),
            ('y-', (x0, y), (x0, -y)),
            ('x+', (x0, -y), (x1, -y)),
            ('y+', (x1, -y), (x1, 0)),
            ('x-', (x1, 0), (x0, 0)),
        ]
        out += [
            {'name': f'{tag} {d}', 'group': tag, 'p0': P(*a, z_high), 'p1': P(*b, z_high), 'speed': v}
            for d, a, b in corners
        ]
    if low_speeds:
        vz = min(VERTICAL_SPEED, max(low_speeds))
        out.append(
            {
                'name': 'sideways to the low line',
                'group': 'transfer',
                'p0': P(x0, 0, z_high),
                'p1': P(x0, low_y, z_high),
                'speed': low_speeds[0],
            }
        )
        out.append(
            {'name': 'down', 'group': 'vertical', 'p0': P(x0, low_y, z_high), 'p1': P(x0, low_y, z_low), 'speed': vz}
        )
        for v in low_speeds:
            tag = f'low {v * 100:g} cm/s'
            out.append(
                {'name': f'{tag} x+', 'group': tag, 'p0': P(x0, low_y, z_low), 'p1': P(x1, low_y, z_low), 'speed': v}
            )
            out.append(
                {'name': f'{tag} x-', 'group': tag, 'p0': P(x1, low_y, z_low), 'p1': P(x0, low_y, z_low), 'speed': v}
            )
        out.append(
            {'name': 'up', 'group': 'vertical', 'p0': P(x0, low_y, z_low), 'p1': P(x0, low_y, z_high), 'speed': vz}
        )
    return [ln for ln in out if np.linalg.norm(ln['p1'] - ln['p0']) > 1e-6]


def check_plan(model: RobotModel, lines: list[dict], home: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> list[str]:
    """Why the plan cannot be run (empty: fine): every 2 cm of every line must be reachable and inside the box."""
    ik, problems, q = DiffIK(model, posture=home), [], home.copy()
    data = model.new_data()
    for ln in [{'name': 'from home', 'p0': model.fk(home)[0], 'p1': lines[0]['p0']}, *lines]:
        n = max(2, int(np.linalg.norm(ln['p1'] - ln['p0']) / 0.02) + 1)
        for s in np.linspace(0.0, 1.0, n):
            p = ln['p0'] + s * (ln['p1'] - ln['p0'])
            r = ik.solve(p, DOWN, q, max_iters=200)
            why = None if r.success else 'out of reach'
            why = why or violation(model, r.q, lo, hi, data)
            if why:
                problems.append(f'{ln["name"]}: at {np.round(p, 3).tolist()} {why}')
                break
            q = r.q
    return problems


def run_line(arm, cart, rec, p1: np.ndarray, speed: float, guard) -> tuple[float, float, float]:
    """Drive the commanded tip to ``p1`` in a straight line, then hold. Returns the arm times (start, arrival, end)."""
    cart.limits.max_speed = speed
    t0 = arm.now()
    t_limit = t0 + np.linalg.norm(p1 - cart.pos) / speed * 2.0 + 5.0
    bad_ik = 0
    while np.linalg.norm(cart.pos - p1) > 1e-5:
        st = cart.step(p1, DOWN)
        rec.add('tcp_target', np.r_[st.pos, st.rot.ravel()])
        bad_ik = 0 if st.ik_ok else bad_ik + 1
        guard()
        if bad_ik * arm.dt > 0.5:
            raise Abort(f'the joint solution fails near {np.round(cart.pos, 3).tolist()}')
        if arm.now() > t_limit:
            raise Abort(
                f'the command did not reach {np.round(p1, 3).tolist()} in time (stuck at {np.round(cart.pos, 3).tolist()})'
            )
        arm.sleep()
    t1 = arm.now()
    while arm.now() - t1 < SETTLE:
        st = cart.hold()
        rec.add('tcp_target', np.r_[st.pos, st.rot.ravel()])
        guard()
        arm.sleep()
    return t0, t1, arm.now()


# ----------------------------------------------------------------------------------------------- analysis
def analyse(model: RobotModel, log: dict, segments: list[dict]) -> list[dict]:
    """Per line: deviations of the measured tip from the ideal line (m), lag behind the command, lean, settled error."""
    t = log['t_arm']
    data = model.new_data()
    tip = np.empty((len(t), 3))
    lean = np.empty(len(t))
    for i, q in enumerate(log['q']):
        p, rot = model.fk(q, data)
        tip[i] = p
        lean[i] = math.degrees(math.acos(float(np.clip(-rot[2, 2], -1.0, 1.0))))
    # the arm log and the extra streams are on the same clock; "tcp_target_t" was shifted to unix time with "t"
    tc = log['tcp_target_t'] - (log['t'][0] - t[0])
    cmd = np.column_stack([np.interp(t, tc, log['tcp_target'][:, k]) for k in range(3)])
    out = []
    for seg in segments:
        p0, p1 = np.array(seg['p0']), np.array(seg['p1'])
        if np.linalg.norm(p1 - p0) < 1e-6:
            continue
        u = (p1 - p0) / np.linalg.norm(p1 - p0)
        m = (t >= seg['t0']) & (t <= seg['t1'])
        e = tip[m] - p0
        s = e @ u
        cross = e - np.outer(s, u)
        vertical_line = abs(u[2]) > 0.9
        side = (
            np.linalg.norm(cross[:, :2], axis=1)
            if vertical_line
            else cross[:, :2] @ np.array([-u[1], u[0]]) / max(np.hypot(u[0], u[1]), 1e-9)
        )
        height = np.zeros(m.sum()) if vertical_line else cross[:, 2]
        behind = (cmd[m] - tip[m]) @ u
        ts, mid = t[m], (s > 0.2 * s.max()) & (s < 0.8 * s.max())
        speed = float(np.polyfit(ts[mid], s[mid], 1)[0]) if mid.sum() > 5 else float('nan')
        ms = (t >= seg['t2'] - 0.2) & (t <= seg['t2'])
        settled = tip[ms].mean(axis=0) - p1
        out.append(
            {
                'name': seg['name'],
                'group': seg['group'],
                'length': float(np.linalg.norm(p1 - p0)),
                'speed_set': seg['speed'],
                'speed': speed,
                'side_max': float(np.abs(side).max()),
                'side_rms': float(np.sqrt((side**2).mean())),
                'height_min': float(height.min()),
                'height_max': float(height.max()),
                'behind_max': float(behind.max()),
                'lean_max': float(lean[m].max()),
                'settled': settled.tolist(),
                'tau_max': np.abs(log['tau'][m]).max(axis=0).tolist(),
            }
        )
    return out


def report(res: list[dict], log: dict) -> dict:
    mm = lambda v: f'{v * 1000:+.1f}'  # noqa: E731
    print(
        f'{"line":24s} {"len":>5s} {"speed":>11s} {"sideways":>13s} {"height":>15s} {"behind":>7s} {"lean":>5s}  settled error (x, y, z)'
    )
    print(
        f'{"":24s} {"cm":>5s} {"set/got cm/s":>11s} {"max / rms mm":>13s} {"min .. max mm":>15s} {"max mm":>7s} {"deg":>5s}  mm'
    )
    for r in res:
        print(
            f'{r["name"]:24s} {r["length"] * 100:5.1f} {r["speed_set"] * 100:5.1f}/{r["speed"] * 100:5.1f} {r["side_max"] * 1000:6.1f} /{r["side_rms"] * 1000:5.1f} '
            f'{mm(r["height_min"]):>7s} ..{mm(r["height_max"]):>6s} {r["behind_max"] * 1000:7.1f} {r["lean_max"]:5.1f}  '
            f'({", ".join(mm(v) for v in r["settled"])})'
        )
    groups: dict[str, dict] = {}
    for r in res:
        g = groups.setdefault(
            r['group'],
            {
                'side_max_mm': 0.0,
                'height_min_mm': 0.0,
                'height_max_mm': 0.0,
                'behind_max_mm': 0.0,
                'settled_max_mm': 0.0,
                'lean_max_deg': 0.0,
            },
        )
        g['side_max_mm'] = round(max(g['side_max_mm'], r['side_max'] * 1000), 2)
        g['height_min_mm'] = round(min(g['height_min_mm'], r['height_min'] * 1000), 2)
        g['height_max_mm'] = round(max(g['height_max_mm'], r['height_max'] * 1000), 2)
        g['behind_max_mm'] = round(max(g['behind_max_mm'], r['behind_max'] * 1000), 2)
        g['settled_max_mm'] = round(max(g['settled_max_mm'], float(np.linalg.norm(r['settled'])) * 1000), 2)
        g['lean_max_deg'] = round(max(g['lean_max_deg'], r['lean_max']), 2)
    print()
    for name, g in groups.items():
        print(
            f'{name:14s}: sideways up to {g["side_max_mm"]:.1f} mm, height {g["height_min_mm"]:+.1f} .. {g["height_max_mm"]:+.1f} mm, '
            f'behind the command up to {g["behind_max_mm"]:.1f} mm, after stopping up to {g["settled_max_mm"]:.1f} mm, lean up to {g["lean_max_deg"]:.1f} deg'
        )
    tau, temp = np.abs(log['tau']).max(axis=0), log['temp'].max(axis=0)
    print(f'largest motor torque {np.round(tau, 2).tolist()} N*m, highest temperature {np.round(temp, 0).tolist()} C')
    return {'groups': groups, 'tau_max': np.round(tau, 3).tolist(), 'temp_max': np.round(temp, 1).tolist()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        '--x', type=float, nargs=2, default=[0.24, 0.37], help='the lines along x run between these (m, arm frame)'
    )
    ap.add_argument('--y', type=float, default=0.10, help='the lines along y run from -y to +y (m)')
    ap.add_argument('--high', type=float, default=0.06, help='height of the pattern above the table (m)')
    ap.add_argument('--low', type=float, default=0.02, help='height of the low line above the table (m)')
    ap.add_argument('--low-y', type=float, default=0.0, help='y of the low line (m)')
    ap.add_argument('--speeds', default='0.03,0.06,0.10', help='speeds of the pattern (m/s)')
    ap.add_argument('--low-speeds', default='0.03,0.06', help="speeds of the low line (m/s); 'none' leaves it out")
    ap.add_argument(
        '--min-clear', type=float, default=0.008, help='abort when the tool is lower than this above the table (m)'
    )
    ap.add_argument(
        '--table-z', type=float, help='table height in the arm frame (m); default: calibration/table.yaml, simulator 0'
    )
    ap.add_argument(
        '--cams', help="cameras to record: 'top,wrist' (default on the real arm) or 'none' (default in the simulator)"
    )
    ap.add_argument(
        '--end', choices=('fold', 'hold'), default='fold', help='fold and torque off, or keep holding at home'
    )
    ap.add_argument('--sim', action='store_true')
    ap.add_argument(
        '--friction-ff',
        type=float,
        help="scale of the friction feedforward for this run (0..1; default: the arm config's, 0). "
        'Needs a friction model in the calibration file',
    )
    ap.add_argument(
        '--ripple-ff',
        type=float,
        help='scale of the torque-ripple feedforward for this run (0..1; default 1 when the '
        'calibration file has a ripple model). 0 switches it off, to compare',
    )
    ap.add_argument(
        '--sim-ripple', action='store_true', help='simulator: the simulated shoulder and elbow have a torque ripple'
    )
    ap.add_argument('--sim-friction', help="simulator: true dry friction of the joints, 'N*m,...' (6 values)")
    ap.add_argument('--sim-start', help="simulator: joint angles at start, 'deg,deg,...' (default: folded)")
    ap.add_argument('--save', action='store_true', help='simulator: keep the episode under data/episodes')
    ap.add_argument('--yes', action='store_true', help='real arm: actually move (default: print the plan only)')
    ap.add_argument('--tool', default=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'))
    ap.add_argument('--calibration', default=str(ROOT / 'calibration' / 'b601_rs.yaml'))
    ap.add_argument('--workspace', default=str(ROOT / 'calibration' / 'workspace.yaml'))
    ap.add_argument('--from-data', help='an episode folder: recompute the report from it, no arm')
    args = ap.parse_args()

    if args.from_data:
        meta, log = load(Path(args.from_data))
        cal = Calibration.load(args.calibration) if Path(args.calibration).is_file() else None
        model = RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(args.tool), cal)
        report(analyse(model, log, meta['segments']), log)
        return 0

    speeds = [float(v) for v in args.speeds.split(',')]
    low_speeds = [] if args.low_speeds == 'none' else [float(v) for v in args.low_speeds.split(',')]
    if max(speeds + low_speeds) > MAX_SPEED or min(speeds + low_speeds) <= 0:
        print(f'REFUSED: speeds must be between 0 and {MAX_SPEED} m/s')
        return 2
    if args.low < args.min_clear + 0.005:
        print(f'REFUSED: the low line must be at least {args.min_clear + 0.005:g} m above the table')
        return 2
    table = args.table_z if args.table_z is not None else 0.0 if args.sim else table_height(Path(args.workspace))
    if table is None:
        print('REFUSED: the table height is not known (run robot/arm_touch_table.py or give --table-z)')
        return 2
    lo, hi = load_workspace(Path(args.workspace))
    lo[2] = table + args.min_clear  # this tool goes below the free-space floor on purpose
    cams = (
        ()
        if (args.cams or ('none' if args.sim else 'top,wrist')) == 'none'
        else tuple(c.strip() for c in (args.cams or 'top,wrist').split(','))
    )

    if args.sim:
        sys.path.insert(0, str(ROOT / 'sim'))
        from scene import make_arm

        q0 = {'q0': np.radians([float(v) for v in args.sim_start.split(',')])} if args.sim_start else {}
        if args.sim_friction:
            q0['truth_friction'] = {'frictionloss': [float(v) for v in args.sim_friction.split(',')]}
        if args.sim_ripple:
            from arm_calib_ripple import SIM_RIPPLE, limited

            q0['truth_ripple'] = SIM_RIPPLE
        arm_cm = make_arm(calibration=Path(args.calibration), **q0)
        if args.sim_ripple:  # the simulator's own ripple as the model, limited like a calibrated one
            arm_cm.cfg.ripple = limited(RippleParams.from_dict(SIM_RIPPLE, arm_cm.n), arm_cm.cfg.gains.kp)[0]
    else:
        arm_cm = Arm.from_config('b601_rs', tool=args.tool, calibration=args.calibration, backend='real')

    if args.friction_ff is not None:
        cal = Calibration.load(args.calibration)
        if not 0.0 <= args.friction_ff <= 1.0 or (args.friction_ff > 0 and cal.friction is None):
            print('REFUSED: --friction-ff must be between 0 and 1, and the calibration file needs a friction model')
            return 2
        arm_cm.cfg.feedforward.friction_scale = args.friction_ff

    if args.ripple_ff is not None:
        if not 0.0 <= args.ripple_ff <= 1.0 or (args.ripple_ff > 0 and arm_cm.cfg.ripple is None):
            print(
                'REFUSED: --ripple-ff must be between 0 and 1, and the calibration file needs a ripple model (robot/arm_calib_ripple.py)'
            )
            return 2
        arm_cm.cfg.feedforward.ripple_scale = args.ripple_ff

    with arm_cm as arm:
        home = np.asarray(arm.tool.home, dtype=float)
        p_home, rot_home = arm.model.fk(home)
        r = float((arm.tool.extra.get('tip') or {}).get('radius', 0.0))
        # heights are those of the tool's lowest point; with the rod straight down that is the TCP
        lines = plan(tuple(args.x), args.y, table + args.high, table + args.low, args.low_y, speeds, low_speeds)
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
        if np.degrees(np.arccos(-rot_home[2, 2])) > 1.0:
            print("REFUSED: this test keeps the rod vertical, and the tool's home pose does not")
            return 2
        problems = check_plan(arm.model, lines, home, lo, hi)
        length = sum(np.linalg.norm(ln['p1'] - ln['p0']) for ln in lines)
        seconds = sum(np.linalg.norm(ln['p1'] - ln['p0']) / ln['speed'] + SETTLE for ln in lines)
        print(
            f'table at z = {table * 1000:+.1f} mm; home: tip {np.round(p_home, 3).tolist()} m, rod vertical (tip ball radius {r * 1000:g} mm)'
        )
        print(f'{len(lines)} lines, {length:.2f} m, about {seconds + 30:.0f} s with the way there and back:')
        print(
            f'  pattern {args.high * 100:g} cm above the table (z = {(table + args.high) * 1000:.0f} mm): x {args.x[0]:.2f}..{args.x[1]:.2f}, '
            f'y {-args.y:+.2f}..{args.y:+.2f} m, at {", ".join(f"{v * 100:g}" for v in speeds)} cm/s'
        )
        if low_speeds:
            print(
                f'  low line {args.low * 100:g} cm above the table (z = {(table + args.low) * 1000:.0f} mm): x {args.x[0]:.2f}..{args.x[1]:.2f} at y = {args.low_y:+.2f} m, '
                f'at {", ".join(f"{v * 100:g}" for v in low_speeds)} cm/s; down and up at {min(VERTICAL_SPEED, max(low_speeds)) * 100:g} cm/s'
            )
        fr = arm.cfg.friction
        print(
            f'  friction feedforward: scale {arm.cfg.feedforward.friction_scale:g}'
            + (f', Coulomb {np.round(fr.fc_pos, 2).tolist()} N*m' if arm.cfg.feedforward.friction_scale > 0 else '')
        )
        rp_on = arm.cfg.ripple is not None and arm.cfg.feedforward.ripple_scale > 0
        print(
            '  torque-ripple feedforward: '
            + (
                f'scale {arm.cfg.feedforward.ripple_scale:g}, amplitude {np.round(arm.cfg.ripple.amplitude(), 2).tolist()} N*m'
                if rp_on
                else 'off'
            )
        )
        print(
            '  recorded: arm log'
            + (f' and cameras {", ".join(cams)}' if cams else ', no cameras')
            + f'; aborts below {args.min_clear * 1000:g} mm above the table; then: {"fold, torque off" if args.end == "fold" else "keep holding at home, enabled"}'
        )
        if abs(roll) > math.radians(5.0) and folded and not at_home:
            print(f'  the tool hangs rolled by {math.degrees(roll):+.0f} deg: joint 6 is levelled first, in place')
        if problems:
            print('REFUSED:\n  ' + '\n  '.join(problems))
            return 2
        if not args.sim and not args.yes:
            print('plan only: nothing moved (add --yes to move the real arm)')
            return 0

        root = DATA if (args.save or not args.sim) else Path(tempfile.mkdtemp(prefix='asfinger-line-'))
        rec = EpisodeRecorder(
            arm,
            label='line-test',
            cams=cams,
            root=root,
            meta={
                'table_z': float(table),
                'calibration': str(args.calibration),
                'friction_ff': float(arm.cfg.feedforward.friction_scale),
                'ripple_ff': float(arm.cfg.feedforward.ripple_scale) if rp_on else 0.0,
                'plan': {k: getattr(args, k) for k in ('x', 'y', 'high', 'low', 'low_y', 'speeds', 'low_speeds')},
            },
        )
        limits = CartesianLimits.from_dict(arm.tool.cartesian)
        xs = [ln[k][0] for ln in lines for k in ('p0', 'p1')] + [p_home[0]]
        ys = [ln[k][1] for ln in lines for k in ('p0', 'p1')] + [p_home[1]]
        limits.x, limits.y = (min(xs) - 0.01, max(xs) + 0.01), (min(ys) - 0.01, max(ys) + 0.01)
        limits.z = (table + (args.low if low_speeds else args.high) - 0.002, max(p_home[2], table + args.high) + 0.02)
        limits.max_ang_speed = 0.5

        def guard() -> None:
            q = arm.q()
            low = lowest_point(arm.model, q, 0.0)[2] - table
            if low < args.min_clear:
                raise Abort(f'the tool is {low * 1000:.1f} mm above the table')
            off = np.linalg.norm(arm.tcp_pose(q)[0] - arm.tcp_pose(arm.filter.q_filt)[0])
            if off > 0.015:
                raise Abort(f'the tip is {off * 1000:.0f} mm from where the motors were told to be')
            if abort_at is not None and len(segments) >= abort_at:
                raise Abort('test of the abort path (ASFINGER_TEST_ABORT)')

        test_abort = os.environ.get(
            'ASFINGER_TEST_ABORT', os.environ.get('IPUSH_TEST_ABORT')
        )  # the earlier name still works
        abort_at = int(test_abort) if args.sim and test_abort is not None else None
        arm.enable()
        go_home(arm)
        cart = arm.cartesian(limits)
        segments, aborted = [], None
        rec.start()  # connects the phones: a missing phone stops the test here, at home
        try:
            run_line(arm, cart, rec, lines[0]['p0'], VERTICAL_SPEED, guard)
            for ln in lines:
                t0, t1, t2 = run_line(arm, cart, rec, ln['p1'], ln['speed'], guard)
                segments.append(
                    {
                        'name': ln['name'],
                        'group': ln['group'],
                        'speed': ln['speed'],
                        'p0': ln['p0'].tolist(),
                        'p1': ln['p1'].tolist(),
                        't0': t0,
                        't1': t1,
                        't2': t2,
                    }
                )
                print(f'  done: {ln["name"]}', flush=True)
        except Abort as e:
            aborted = str(e)
            print(f'ABORTED: {aborted}. Lifting the tip straight up, then home.', flush=True)
            cart.limits.max_speed = 0.02
            up = cart.pos.copy()
            up[2] = table + args.high
            t_end = arm.now() + 8.0
            while np.linalg.norm(cart.pos - up) > 1e-5 and arm.now() < t_end:
                cart.step(up, None)
                arm.sleep()
        finally:
            rec.note(segments=segments, aborted=aborted)
            path = rec.stop(complete=aborted is None)
        arm.move_to_joint(home, speed=math.radians(15.0))
        if args.end == 'hold':
            arm.detach()
        else:
            print('folding to the zero pose, then torque off', flush=True)

    meta, log = load(path)
    if segments:
        result = report(
            analyse(
                RobotModel(ArmConfig.load('b601_rs'), ToolConfig.load(args.tool), Calibration.load(args.calibration)),
                log,
                segments,
            ),
            log,
        )
        meta['result'] = result
        (path / 'meta.yaml').write_text(yaml.safe_dump(meta, sort_keys=False, allow_unicode=True, width=140))
    print()
    if args.save or not args.sim:
        print(describe(path))
    else:
        shutil.rmtree(path.parent)  # simulator without --save: the episode was only needed for the report
    return 0 if aborted is None else 1


if __name__ == '__main__':
    sys.exit(main())
