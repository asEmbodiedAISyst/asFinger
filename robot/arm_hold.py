"""Hold the arm where it is with torque on, log what the motors do, then switch torque off. No other motion.

    uv run python robot/arm_hold.py --sim                           # always try in simulation first
    uv run python robot/arm_hold.py --seconds 60 --record hold.npz
    uv run python robot/arm_hold.py --seconds 60 --kd 2.4,8,8,4,3.2,3.2 --record hold_kd8.npz

Gains come from calibration/b601_rs.yaml (this arm's calibration) unless --kp / --kd are given.

Real arm: only with the operator at the motor power switch, after telling them what will happen
(docs/en/user/robot-arm-tools.md). Unlike `rebot-control hold`, this never folds the arm to its zero pose on exit.

Start it with torque off and the arm in a pose it can rest in (the folded pose): the run ends with torque off.
It stops early, also with torque off, when a joint moves more than --max-move from where it started, a driver
gets hotter than --max-temp, or on Ctrl-C. Torque off lets every joint go limp: the tool rolls about joint 6
unless it already hangs at its rest angle.

Any other failure follows the library's rule: the arm holds where it is and stays enabled
(docs/user/safety.md of the rebot-control repository); end that with `rebot-control release`.
"""

from __future__ import annotations

import argparse
import math
import signal
import sys

from pathlib import Path

import numpy as np
from rebot_control import Arm

CALIBRATION = Path(__file__).resolve().parent.parent / 'calibration' / 'b601_rs.yaml'


def _floats(text: str) -> np.ndarray:
    values = np.array([float(v) for v in text.split(',')])
    if len(values) != 6:
        raise argparse.ArgumentTypeError('expected 6 comma-separated numbers, one per joint')
    return values


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--sim', action='store_true', help='simulator instead of the real arm')
    ap.add_argument('--tool', default=str(CALIBRATION.with_name('tool_ip17pro_print.yaml')))
    ap.add_argument('--seconds', type=float, default=8.0)
    ap.add_argument(
        '--calibration', default=str(CALIBRATION), help="calibration YAML, or 'none' for the library defaults"
    )
    ap.add_argument('--kp', type=_floats, help='MIT kp per joint for this run (default: from the calibration)')
    ap.add_argument('--kd', type=_floats, help='MIT kd per joint for this run (default: from the calibration)')
    ap.add_argument('--max-move', type=float, default=3.0, help='deg; abort when a joint moves further than this')
    ap.add_argument('--max-temp', type=float, default=60.0, help='deg C; abort when a driver gets hotter than this')
    ap.add_argument('--report-every', type=float, default=2.0, help='s between printed lines')
    ap.add_argument('--record', help='save the 150 Hz servo log to this .npz')
    args = ap.parse_args()

    def _terminate(*_):  # a killed process would leave the motors on their last frame
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, _terminate)

    deg = lambda a: np.array2string(np.degrees(a), precision=2, suppress_small=True, floatmode='fixed')
    rec: dict[str, np.ndarray] = {}
    calibration = None if args.calibration == 'none' else args.calibration
    with Arm.from_config(
        'b601_rs', tool=args.tool, calibration=calibration, backend='sim' if args.sim else 'real'
    ) as arm:
        if arm.taken_over:
            print(
                'The motors are already enabled and holding the arm (left by another program). This tool only starts '
                'from torque off: end the hold first with `robot/arm release` (hand on the arm) '
                'or `... release --fold`. Nothing was changed.'
            )
            return 3
        if args.kp is not None or args.kd is not None:
            arm.set_gains(args.kp, args.kd)
        q0 = arm.q().copy()
        print(f'start q {deg(q0)} deg | kp {arm.servo.kp.tolist()} kd {arm.servo.kd.tolist()}', flush=True)
        print(f'torque on (gains ramp in over {arm.cfg.gains.ramp_s} s), holding for {args.seconds:g} s', flush=True)
        reason = 'done'
        try:
            arm.enable()
            arm.start_recording()
            t0 = arm.now()
            while arm.now() - t0 < args.seconds - 0.1:
                arm.wait(min(args.report_every, args.seconds))
                st = arm.state()
                print(
                    f'{arm.now() - t0:5.1f} s | moved {deg(st.q - q0)} deg | tau {np.round(st.tau, 2).tolist()} N*m | '
                    f'temp {st.temp.round(0).astype(int).tolist()} C | enabled {st.enabled.astype(int).tolist()} | '
                    f'overruns {arm.servo.overruns}',
                    flush=True,
                )
                if np.abs(st.q - q0).max() > math.radians(args.max_move):
                    reason = f'a joint moved more than {args.max_move:g} deg'
                    break
                if st.temp.max() > args.max_temp:
                    reason = f'a driver is hotter than {args.max_temp:g} C'
                    break
        except KeyboardInterrupt:
            reason = 'interrupted'
        rec = arm.stop_recording()
        arm.disable_torque()  # no fold: the run started from a rest pose
        print(f'torque off ({reason}); the arm was not folded', flush=True)
        arm.sleep(0.5)
        print(f'end   q {deg(arm.q())} deg', flush=True)

    if len(rec.get('t', [])):
        t = rec['t']
        keep = t > t[0] + 1.0  # skip the gain ramp
        print(f'torque std   {np.round(rec["tau"][keep].std(0), 3).tolist()} N*m')
        print(f'velocity std {np.round(np.degrees(rec["dq"][keep].std(0)), 2).tolist()} deg/s')
        print(
            f'temperature  {rec["temp"][0].round(0).astype(int).tolist()} -> {rec["temp"][-1].round(0).astype(int).tolist()} C'
        )
        if args.record:
            np.savez(args.record, **rec)
            print(f'servo log: {args.record} ({len(t)} samples)')
    return 0 if reason == 'done' else 1


if __name__ == '__main__':
    sys.exit(main())
