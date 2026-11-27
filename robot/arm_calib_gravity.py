"""Gravity calibration of this arm inside its box: static poses -> link masses and centres of mass.

    uv run python robot/arm_calib_gravity.py --sim                 # try the whole procedure in simulation
    uv run python robot/arm_calib_gravity.py                       # real arm: prints the poses, moves nothing
    uv run python robot/arm_calib_gravity.py --yes                 # real arm: runs it (about 5 min for 20 poses)
    uv run python robot/arm_calib_gravity.py --preset board --yes  # poses over the whiteboard instead
    uv run python robot/arm_calib_gravity.py --from-data calibration/data/gravity-*.npz      # refit, no arm

What it does: unfolds to the tool's home pose, visits --poses random poses (each from both sides, so that static
friction averages out), holds still at each one and averages the motor torques, returns home, folds and switches
torque off. Then it fits every link's mass and centre of mass (tool included, as mounted) and writes them to
calibration/b601_rs.yaml, keeping what is already there (gains). The raw data goes to calibration/data/.

The fit always starts from the URDF model, not from an earlier calibration, so running it again or refitting old
data gives the same answer. By default it fits no per-joint torque offset: the library does not use that offset
for control, so whatever it absorbs is missing from the feedforward (on this arm 0.3-0.5 N*m on shoulder, elbow
and wrist flex, while the motors' torque reading is within 0.2 N*m of what they are asked for). --fit-bias turns
it on. Expect the fitted model to be right to about the joints' static friction (0.1-0.4 N*m) inside the range of
the poses, and worse outside it.

The library's own `rebot-control calib gravity` only keeps the arm off the table and the base column. This tool
generates the poses itself, with narrower joint ranges, and keeps every pose and every move between two poses
- inside calibration/workspace.yaml (the box, minus its margin),
- above --table-z, and
- with the tool at least --tool-clearance away from the base, upper arm and forearm (the phone on the tool is not
  in the model; the distance is measured from the tool's axis).
The checks know nothing about cables or objects on the table. Clear the table and watch the arm.

Real arm: only with the operator at the motor power switch, after telling them what will happen
(docs/en/user/robot-arm-tools.md). A failure leaves the arm holding where it is (`robot/arm release` ends that).
"""

from __future__ import annotations

import argparse
import datetime as dt
import math
import signal
import sys
from pathlib import Path

import numpy as np
from rebot_control import Arm, RobotModel
from rebot_control.calib.gravity import collect_static, fit_gravity
from rebot_control.calib.poses import segment_points
from rebot_control.config import Calibration

from arm_move import load_workspace

ROOT = Path(__file__).resolve().parent.parent
# Joint ranges (deg) for the poses, and the highest tool tip (m).
PRESETS = {
    # arm in front of the base, well inside the box, moderate wrist angles
    'wide': (np.array([[-35, 35], [15, 75], [30, 110], [-60, 30], [-35, 35], [-50, 50]], dtype=float), 0.50),
    # where pushing happens: arm stretched forward and low over the whiteboard, wrist near straight
    'board': (np.array([[-35, 35], [30, 100], [15, 70], [-40, 25], [-30, 30], [-30, 30]], dtype=float), 0.30),
}


def _segment_distance(p: np.ndarray, a: np.ndarray, b: np.ndarray) -> float:
    ab = b - a
    t = np.clip(np.dot(p - a, ab) / max(float(np.dot(ab, ab)), 1e-12), 0.0, 1.0)
    return float(np.linalg.norm(p - (a + t * ab)))


def why_not(
    model,
    q: np.ndarray,
    lo: np.ndarray,
    hi: np.ndarray,
    table_z: float,
    tool_clearance: float,
    tip_z_max: float = np.inf,
) -> str | None:
    """Why the pose is not allowed, or None."""
    joints = model.link_positions(q)  # joint centres 1..6, then the tool tip
    if joints[-1, 2] > tip_z_max:
        return 'tool tip too high'
    pts = segment_points(joints[2:])
    for axis, name in enumerate('xyz'):
        if (pts[:, axis] < lo[axis]).any() or (pts[:, axis] > hi[axis]).any():
            return f'outside the box in {name}'
    if (pts[:, 2] < table_z).any():
        return 'too close to the table'
    tool = segment_points(joints[-2:], per_segment=6)  # wrist roll centre -> tool tip
    for a, b in ((joints[0], joints[1]), (joints[1], joints[2]), (joints[2], joints[3])):  # base, upper arm, forearm
        if min(_segment_distance(p, a, b) for p in tool) < tool_clearance:
            return 'tool too close to the arm'
    return None


def make_poses(model, n: int, start: np.ndarray, rng: np.random.Generator, check, ranges_deg: np.ndarray) -> np.ndarray:
    """``n`` allowed poses, spread out, ordered as a short tour from ``start`` with every move allowed too."""
    lo = np.maximum(np.radians(ranges_deg[:, 0]), model.lower + 0.05)
    hi = np.minimum(np.radians(ranges_deg[:, 1]), model.upper - 0.05)
    cands = []
    for _ in range(40000):
        q = rng.uniform(lo, hi)
        if check(q) is None:
            cands.append(q)
            if len(cands) >= 4 * n:
                break
    if len(cands) < n:
        raise RuntimeError(f'only {len(cands)} allowed poses found')
    cands = np.array(cands)
    chosen = [int(np.argmax(np.abs(cands - start).max(axis=1)))]  # farthest-point sampling
    dmin = np.abs(cands - cands[chosen[0]]).max(axis=1)
    while len(chosen) < n:
        i = int(np.argmax(dmin))
        chosen.append(i)
        dmin = np.minimum(dmin, np.abs(cands - cands[i]).max(axis=1))
    path_ok = lambda a, b: all(check(a + s * (b - a)) is None for s in np.linspace(0.0, 1.0, 16))
    todo, tour, cur = [cands[i] for i in chosen], [], np.asarray(start, dtype=float)
    while todo:  # greedy nearest neighbour, allowed moves only
        order = np.argsort([np.abs(q - cur).max() for q in todo])
        for k in order:
            if path_ok(cur, todo[k]):
                cur = todo.pop(int(k))
                tour.append(cur)
                break
        else:
            todo.pop(int(order[0]))
    return np.array(tour)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--poses', type=int, default=20)
    ap.add_argument(
        '--preset', choices=sorted(PRESETS), default='wide', help='which part of the workspace the poses cover'
    )
    ap.add_argument('--seed', type=int, default=0)
    ap.add_argument('--speed', type=float, default=15.0, help='deg/s of the fastest joint between poses')
    ap.add_argument('--settle', type=float, default=1.0, help='s at rest before the torques are averaged')
    ap.add_argument('--table-z', type=float, default=0.06, help='lowest height of the joint centres and tool tip (m)')
    ap.add_argument(
        '--z-max',
        type=float,
        default=0.50,
        help='highest point of the joint centres and tool tip (m); '
        'lower than the box allows, to stay well below the lights and the overhead phone',
    )
    ap.add_argument(
        '--y-max',
        type=float,
        default=0.25,
        help='largest sideways distance of the joint centres and tool '
        'tip (m): the side walls are cloth and the phone sticks out from the tool',
    )
    ap.add_argument('--tool-clearance', type=float, default=0.12, help='tool axis to base / upper arm / forearm (m)')
    ap.add_argument(
        '--prior-rel',
        type=float,
        default=1.0,
        help='how far the masses may move from the current model (relative standard deviation of the prior)',
    )
    ap.add_argument(
        '--fit-bias', action='store_true', help='also fit a constant torque offset per joint (not used for control)'
    )
    ap.add_argument('--bias-std', type=float, default=0.1, help='N*m, with --fit-bias: how large that offset may be')
    ap.add_argument('--sim', action='store_true')
    ap.add_argument('--yes', action='store_true', help='real arm: actually run (default: print the poses only)')
    ap.add_argument(
        '--from-data', nargs='+', help='fit saved .npz files (several are fitted together) instead of moving the arm'
    )
    ap.add_argument('--no-save', action='store_true', help='do not write the calibration file')
    ap.add_argument('--tool', default=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'))
    ap.add_argument('--calibration', default=str(ROOT / 'calibration' / 'b601_rs.yaml'))
    ap.add_argument('--workspace', default=str(ROOT / 'calibration' / 'workspace.yaml'))
    args = ap.parse_args()

    def _terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _terminate)

    cal_path = Path(args.calibration)
    calibration = str(cal_path) if cal_path.is_file() else None
    arm = Arm.from_config(
        'b601_rs', tool=args.tool, calibration=calibration, backend='sim' if args.sim or args.from_data else 'real'
    )

    if args.from_data:
        sets = [dict(np.load(f)) for f in args.from_data]
        data = {k: np.concatenate([d[k] for d in sets]) for k in ('q', 'tau', 'tau_std', 'side')}
        print(f'fitting {len(data["q"]) // 2} poses from {len(sets)} file(s)')
    else:
        ranges_deg, tip_z_max = PRESETS[args.preset]
        lo, hi = load_workspace(Path(args.workspace))
        hi[2] = min(hi[2], args.z_max)
        lo[1], hi[1] = max(lo[1], -args.y_max), min(hi[1], args.y_max)
        check = lambda q: why_not(arm.model, q, lo, hi, args.table_z, args.tool_clearance, tip_z_max)
        poses = make_poses(arm.model, args.poses, arm.tool.home, np.random.default_rng(args.seed), check, ranges_deg)
        tips = np.array([arm.model.fk(q)[0] for q in poses])
        print(f'{len(poses)} poses (deg) and tool tip (m):')
        for q, p in zip(poses, tips):
            print(
                f'  {np.array2string(np.degrees(q), precision=0, suppress_small=True, floatmode="fixed")}   tip {np.round(p, 2).tolist()}'
            )
        span = float(sum(np.abs(b - a).max() for a, b in zip(np.vstack([arm.tool.home, poses[:-1]]), poses)))
        minutes = (
            2 * len(poses) * (args.settle + 0.5 + 0.8)
            + (span + 2 * len(poses) * math.radians(6)) / math.radians(args.speed)
        ) / 60
        print(
            f'tool tip range: x {tips[:, 0].min():.2f}..{tips[:, 0].max():.2f}, y {tips[:, 1].min():+.2f}..{tips[:, 1].max():+.2f}, '
            f'z {tips[:, 2].min():.2f}..{tips[:, 2].max():.2f} m; about {minutes:.0f} min at {args.speed:g} deg/s'
        )
        if not args.sim and not args.yes:
            print('plan only: nothing moved (add --yes to run it on the real arm)')
            return 0
        with arm:
            start = arm.q().copy()
            arm.enable()
            # level the wrist first if the tool hangs: the staged unfold starts from the folded pose
            level = arm.joint_target()
            level[[0, 4, 5]] = arm.cfg.poses.zero[[0, 4, 5]]
            arm.move_to_joint(level, speed=math.radians(args.speed), settle=0.3)
            arm.move_home(speed=math.radians(args.speed))
            data = collect_static(
                arm,
                poses,
                settle_s=args.settle,
                speed=math.radians(args.speed),
                progress=lambda s: print(f'{s} | temp max {arm.state().temp.max():.0f} C', flush=True),
            )
            arm.move_to_joint(arm.tool.home, speed=math.radians(args.speed))
            print(
                f'done; folding to the zero pose, then torque off (started at {np.round(np.degrees(start), 0).tolist()} deg)',
                flush=True,
            )
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S')
        out = ROOT / 'calibration' / 'data' / f'gravity-{args.preset}-{stamp}{"-sim" if args.sim else ""}.npz'
        out.parent.mkdir(parents=True, exist_ok=True)
        np.savez(out, **data)
        print(f'raw data: {out}')

    prior = RobotModel(arm.cfg, arm.tool)  # the URDF model: the fit does not build on an earlier one
    fit = fit_gravity(prior, data, prior_rel=args.prior_rel, bias_std=args.bias_std, fit_bias=args.fit_bias)
    print(fit.summary(arm.cfg.joints))
    # each pose was measured from both sides: half their difference is static friction, their mean is what the
    # gravity model has to explain
    q2, t2 = np.asarray(data['q']), np.asarray(data['tau'])
    qm, tm, half = (q2[0::2] + q2[1::2]) / 2, (t2[0::2] + t2[1::2]) / 2, (t2[0::2] - t2[1::2]) / 2
    fitted = RobotModel(arm.cfg, arm.tool, Calibration(link_params=fit.link_params))
    for name, m in (('URDF model  ', prior), ('fitted model', fitted)):
        r = tm - np.array([m.gravity(q) for q in qm])
        print(
            f'{name}: error of the two-sided mean, mean {np.round(r.mean(0), 2).tolist()}, RMS {np.round(np.sqrt((r**2).mean(0)), 2).tolist()} N*m'
        )
    print(
        f'static friction (half the two-sided difference), RMS {np.round(np.sqrt((half**2).mean(0)), 2).tolist()} N*m'
    )
    print(fit.info)
    if args.no_save or (args.sim and not args.from_data):
        print('calibration file not written')
        return 0
    base = Calibration.load(cal_path) if cal_path.is_file() else Calibration()
    meta = {
        'gravity_date': dt.datetime.now().isoformat(timespec='seconds'),
        'gravity_tool': args.tool,
        'gravity_poses': int(len(data['q']) // 2),
        'gravity_prior_rel': args.prior_rel,
        'gravity_fit_bias': bool(args.fit_bias),
        'gravity_rms_before': np.round(fit.rms_before, 3).tolist(),
        'gravity_rms_after': np.round(fit.rms_after, 3).tolist(),
        'gravity_bias': np.round(fit.bias, 3).tolist(),
    }
    base.merge(Calibration(link_params=fit.link_params, meta=meta)).save(cal_path)
    print(f'saved {cal_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
