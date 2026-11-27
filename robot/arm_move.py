"""Slow joint-space moves through a list of waypoints, checked against the box the arm stands in.

    uv run python robot/arm_move.py --waypoints "0,=,=,=,0,0; 0,15,20,=,0,0; 0,s,s,=,0,0" --sim
    uv run python robot/arm_move.py --waypoints "..."            # real arm: prints the plan, moves nothing
    uv run python robot/arm_move.py --waypoints "..." --yes      # real arm: moves

A waypoint is six joint angles in degrees, in joint order. `=` keeps the joint where the previous waypoint left it
(for the first waypoint: where it is now) and `s` means the angle the joint had when the program started.

Before anything moves, every waypoint and the straight joint-space path to it are checked against
calibration/workspace.yaml: the joint centres and the tool tip must stay inside the box, minus its margin, and
above the table clearance. A plan that fails the check is refused. The check knows nothing about the arm hitting
itself, the phone on the tool, or objects on the table: use sequences known to be safe and keep the table clear.

Real arm: only with the operator at the motor power switch, after telling them what will happen
(docs/en/user/robot-arm-tools.md). Without --yes nothing moves.

What happens at the end (--end):
    hold  (default) the arm stays enabled and holds the last waypoint after the program exits; the next program
          takes the hold over, and the operator ends it with `rebot-control release`
    off   torque off at the last waypoint: only when that is a pose the arm can rest in
    fold  fold to the zero pose in stages, then torque off

Ctrl-C, a stall or any other failure never switch torque off: the arm holds where it is and stays enabled
(docs/user/safety.md of the rebot-control repository). If the motors are already enabled when this starts, it takes the hold
over and moves on from there.
"""

from __future__ import annotations

import argparse
import math
import signal
import sys
from pathlib import Path

import numpy as np
import yaml
from rebot_control import Arm
from rebot_control.calib.poses import segment_points

ROOT = Path(__file__).resolve().parent.parent
MAX_SPEED_DEG_S = 30.0


def load_workspace(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Lower and upper bounds (m) for the checked points: the box shrunk by its margin, floor at the table clearance.

    The floor is ``table_clearance`` above the table: the highest touched point in ``table.yaml`` next to the
    workspace file (written by arm_touch_table.py), or z = 0 while the table has not been measured.
    """
    w = yaml.safe_load(path.read_text())
    lo = np.array([w['box'][k][0] + w['margin'] for k in 'xyz'])
    hi = np.array([w['box'][k][1] - w['margin'] for k in 'xyz'])
    table = path.with_name('table.yaml')
    z_table = float(yaml.safe_load(table.read_text())['table']['z_max']) if table.is_file() else 0.0
    lo[2] = z_table + w['table_clearance']
    return lo, hi


def violation(model, q: np.ndarray, lo: np.ndarray, hi: np.ndarray, data=None) -> str | None:
    """Why the pose is outside the workspace, or None. Checks points along the links from joint 3 to the tool tip."""
    pts = segment_points(model.link_positions(q, data)[2:])
    for axis, name in enumerate('xyz'):
        if (pts[:, axis] < lo[axis]).any():
            return f'{name} = {pts[:, axis].min():.3f} m is below {lo[axis]:.3f}'
        if (pts[:, axis] > hi[axis]).any():
            return f'{name} = {pts[:, axis].max():.3f} m is above {hi[axis]:.3f}'
    return None


def start_pose(arm) -> tuple[bool, bool, float]:
    """(folded, at_home, roll of joint 6 in rad) of the arm as it is now.

    With the torque off the unbalanced tool rolls about joint 6; that still counts as folded (up to 100 deg), and
    :func:`go_home` levels the wrist before it unfolds.
    """
    q = arm.q()
    off = np.abs(q - arm.cfg.poses.zero)
    folded = bool(off[:5].max() < math.radians(15.0) and off[5] < math.radians(100.0))
    at_home = bool(np.abs(q - arm.tool.home).max() < math.radians(5.0))
    return folded, at_home, float(q[5] - arm.cfg.poses.zero[5])


def go_home(arm, speed: float = math.radians(15.0)) -> None:
    """From the folded pose (tool hanging or not) or from anywhere near home to the tool's home pose. Torque must be on."""
    folded, at_home, _ = start_pose(arm)
    if folded and not at_home:
        level = arm.joint_target()
        level[[0, 4, 5]] = arm.cfg.poses.zero[[0, 4, 5]]
        arm.move_to_joint(level, speed=speed, settle=0.3)
    arm.move_home(speed=speed)


def table_height(workspace: Path) -> float | None:
    """Height of the table in the arm frame from table.yaml next to the workspace file (None: not measured)."""
    table = Path(workspace).with_name('table.yaml')
    return float(yaml.safe_load(table.read_text())['table']['z']) if table.is_file() else None


def parse_waypoints(text: str, start: np.ndarray) -> list[np.ndarray]:
    out, prev = [], start.copy()
    for part in filter(None, (p.strip() for p in text.split(';'))):
        tokens = [t.strip() for t in part.split(',')]
        if len(tokens) != len(start):
            raise ValueError(f"waypoint '{part}' needs {len(start)} values")
        q = prev.copy()
        for j, tok in enumerate(tokens):
            if tok == 's':
                q[j] = start[j]
            elif tok != '=':
                q[j] = math.radians(float(tok))
        out.append(q)
        prev = q
    if not out:
        raise ValueError('no waypoints given')
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--waypoints', required=True, help="'a,b,c,d,e,f; ...' in degrees; '=' keeps, 's' = start value")
    ap.add_argument(
        '--speed', type=float, default=15.0, help=f'deg/s of the fastest joint (at most {MAX_SPEED_DEG_S:g})'
    )
    ap.add_argument('--hold', type=float, default=2.0, help='seconds to hold at each waypoint')
    ap.add_argument('--end', choices=('hold', 'off', 'fold'), default='hold')
    ap.add_argument('--sim', action='store_true')
    ap.add_argument('--yes', action='store_true', help='real arm: actually move (default: print the plan only)')
    ap.add_argument('--tool', default=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'))
    ap.add_argument('--calibration', default=str(ROOT / 'calibration' / 'b601_rs.yaml'))
    ap.add_argument('--workspace', default=str(ROOT / 'calibration' / 'workspace.yaml'))
    ap.add_argument('--record', help='save the 150 Hz servo log to this .npz')
    args = ap.parse_args()
    if not 0 < args.speed <= MAX_SPEED_DEG_S:
        ap.error(f'--speed must be between 0 and {MAX_SPEED_DEG_S:g} deg/s')

    def _terminate(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _terminate)

    lo, hi = load_workspace(Path(args.workspace))
    deg = lambda a: np.array2string(np.degrees(a), precision=1, suppress_small=True, floatmode='fixed')
    rec: dict[str, np.ndarray] = {}
    with Arm.from_config(
        'b601_rs', tool=args.tool, calibration=args.calibration, backend='sim' if args.sim else 'real'
    ) as arm:
        start = arm.q().copy()
        waypoints = parse_waypoints(args.waypoints, start)

        # ---- plan and check ----
        print(
            f'start        q {deg(start)} deg, tip {np.round(arm.tcp_pose(start)[0], 3).tolist()} m'
            + ('  (motors already enabled: taking the hold over)' if arm.taken_over else '')
        )
        problems, prev, total = [], start, 0.0
        for k, q in enumerate(waypoints, 1):
            limited = np.clip(q, arm.model.lower, arm.model.upper)
            if np.abs(limited - q).max() > math.radians(1.0):
                problems.append(f'waypoint {k}: outside the joint limits')
            q = waypoints[k - 1] = limited  # a joint resting a fraction of a degree past its limit is fine
            for s in np.linspace(0.0, 1.0, 21)[1:]:
                why = violation(arm.model, prev + s * (q - prev), lo, hi)
                if why:
                    problems.append(f'waypoint {k}: {why}' + ('' if s == 1.0 else f' on the way ({100 * s:.0f} %)'))
                    break
            seconds = float(np.abs(q - prev).max()) / math.radians(args.speed)
            total += seconds + args.hold
            print(
                f'waypoint {k:2d}  q {deg(q)} deg, tip {np.round(arm.tcp_pose(q)[0], 3).tolist()} m, '
                f'largest joint move {math.degrees(np.abs(q - prev).max()):.1f} deg in {seconds:.1f} s'
            )
            prev = q
        ending = {
            'hold': 'keep holding the last waypoint, enabled',
            'off': 'torque off at the last waypoint',
            'fold': 'fold, torque off',
        }[args.end]
        print(f'about {total:.0f} s in all at {args.speed:g} deg/s; then: {ending}')
        if problems:
            print('REFUSED:\n  ' + '\n  '.join(problems))
            return 2
        if not args.sim and not args.yes:
            print('plan only: nothing moved (add --yes to move the real arm)')
            return 0  # a held arm is left held: this program commanded nothing

        # ---- move ----
        arm.enable()
        arm.start_recording()
        try:
            for k, q in enumerate(waypoints, 1):
                arm.move_to_joint(q, speed=math.radians(args.speed), settle=0.3)
                arm.wait(args.hold)
                st = arm.state()
                print(
                    f'at waypoint {k}: error {deg(st.q - q)} deg | tau {np.round(st.tau, 2).tolist()} N*m | '
                    f'temp max {st.temp.max():.0f} C | tip {np.round(arm.tcp_pose(st.q)[0], 3).tolist()} m',
                    flush=True,
                )
        finally:
            rec = arm.stop_recording()  # on a failure the library holds the arm where it is: nothing to do here
        if args.end == 'hold':
            arm.detach()
            print('holding the last waypoint with torque ON; end it with `rebot-control release`', flush=True)
        elif args.end == 'off':
            arm.disable_torque()
            print('torque off', flush=True)
        else:
            print('folding to the zero pose, then torque off', flush=True)  # done by the normal exit below
    if args.record and len(rec.get('t', [])):
        np.savez(args.record, **rec)
        print(f'servo log: {args.record} ({len(rec["t"])} samples)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
