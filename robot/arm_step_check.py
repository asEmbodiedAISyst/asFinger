"""Small-step check of the position gains at the tool's home pose: overshoot, rise and settling time per joint.

    uv run python robot/arm_step_check.py --joints 1            # real arm: print the plan only, nothing moves
    uv run python robot/arm_step_check.py --joints 1 --yes      # real arm: run it
    uv run python robot/arm_step_check.py --joints 1 --sim

Run it after changing kp or kd in calibration/b601_rs.yaml. From the folded pose (or home) the arm goes to the home
pose, then each joint in --joints jumps by +amplitude and back while the others hold, and the response is measured
(rebot_control.calib.gains.step_response). Then fold and torque off. A joint that buzzes, squeals or keeps swinging
has too much gain or too little damping: switch the power off.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from arm_move import go_home, start_pose  # noqa: E402
from rebot_control import Arm  # noqa: E402
from rebot_control.calib.gains import step_response  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--joints', required=True, help="joints to step, numbered from 1, e.g. '1' or '1,2,3'")
    ap.add_argument('--amplitude', type=float, default=2.0, help='step size (deg), at most 3')
    ap.add_argument(
        '--end', choices=('fold', 'hold'), default='fold', help='fold and torque off, or keep holding at home'
    )
    ap.add_argument('--sim', action='store_true')
    ap.add_argument('--yes', action='store_true', help='real arm: actually move (default: print the plan only)')
    ap.add_argument('--tool', default=str(ROOT / 'calibration' / 'tool_ip17pro_print.yaml'))
    ap.add_argument('--calibration', default=str(ROOT / 'calibration' / 'b601_rs.yaml'))
    args = ap.parse_args()
    joints = [int(j) - 1 for j in args.joints.split(',')]
    if not 0 < args.amplitude <= 3.0:
        print('REFUSED: the step must be between 0 and 3 deg')
        return 2
    if args.sim:
        sys.path.insert(0, str(ROOT / 'sim'))
        from scene import make_arm

        arm_cm = make_arm(calibration=Path(args.calibration))
    else:
        arm_cm = Arm.from_config('b601_rs', tool=args.tool, calibration=args.calibration, backend='real')
    arm_cm.cfg.feedforward.ripple_scale = 0.0  # the plain position loop is what is being checked
    with arm_cm as arm:
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
        home = np.asarray(arm.tool.home, dtype=float)
        lever = [
            float(np.linalg.norm(np.cross(np.eye(3)[2], arm.model.fk(home)[0]))) if j == 0 else None for j in joints
        ]
        print(
            f'gains kp {arm.cfg.gains.kp.tolist()}, kd {arm.cfg.gains.kd.tolist()}; ripple feedforward off for this check'
        )
        print(
            f'at home (tip {np.round(arm.model.fk(home)[0], 3).tolist()} m): joints {[j + 1 for j in joints]} step by {args.amplitude:g} deg and back, one at a time'
            + (
                f' (joint 1: the tip jumps about {math.radians(args.amplitude) * lever[0] * 1000:.0f} mm sideways)'
                if 0 in joints
                else ''
            )
            + f'; then: {"fold, torque off" if args.end == "fold" else "keep holding at home, enabled"}'
        )
        if abs(roll) > math.radians(5.0) and folded and not at_home:
            print(f'  the tool hangs rolled by {math.degrees(roll):+.0f} deg: joint 6 is levelled first, in place')
        if not args.sim and not args.yes:
            print('plan only: nothing moved (add --yes to move the real arm)')
            return 0
        arm.enable()
        go_home(arm)
        for j in joints:
            print(
                f'{arm.cfg.joints[j]} (inertia seen by the joint {arm.model.mass_matrix(arm.q())[j, j]:.3f} kg*m^2):',
                flush=True,
            )
            for m in step_response(arm, j, amplitude=math.radians(args.amplitude)):
                print(f'  {m.line()}', flush=True)
            arm.move_to_joint(home, speed=math.radians(15.0))
        if args.end == 'hold':
            arm.detach()
        else:
            print('folding to the zero pose, then torque off', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
