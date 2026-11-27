"""Ask every motor for its angle, over and over, and count the answers. Read only: nothing is enabled, moved or released.

    uv run python robot/arm_bus_check.py                 # 30 s
    uv run python robot/arm_bus_check.py --seconds 120   # longer, e.g. while moving the arm by hand, torque off

For finding a bad cable or connector: with the torque off, move the arm by hand through the poses where the
trouble showed and watch which motors stop answering. Motors that hold keep holding, motors that are off stay off.
No other program may be connected to the arm (the bus is locked by whoever has it).

Why not `robot/arm state` in a loop: that stops at the first motor that does not answer. And the running tools
cannot show it either: the servo loop keeps a motor's last feedback when no new one arrives.
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
import time

import numpy as np


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--seconds', type=float, default=30.0)
    ap.add_argument('--timeout-ms', type=int, default=100, help='how long to wait for one answer')
    args = ap.parse_args()
    logging.basicConfig(level=logging.ERROR)
    from rebot_control import ArmConfig
    from rebot_control.backends.robstride import PARAM_MECH_POS, RobStrideBackend

    cfg = ArmConfig.load('b601_rs')
    backend = RobStrideBackend(cfg)
    backend.connect()
    n = len(backend.motors)
    asked, missed, run, longest = np.zeros(n, int), np.zeros(n, int), np.zeros(n, int), np.zeros(n, int)
    q = np.full(n, np.nan)
    lo, hi = np.full(n, np.inf), np.full(n, -np.inf)
    t0 = t_print = time.monotonic()
    print(
        f'asking {n} motors for {args.seconds:g} s (Ctrl-C stops). Each column: joint angle in deg, or -- for no answer; then answers missed so far'
    )
    try:
        while time.monotonic() - t0 < args.seconds:
            for i, motor in enumerate(backend.motors):
                asked[i] += 1
                try:
                    raw = float(motor.robstride_get_param_f32(PARAM_MECH_POS, args.timeout_ms))
                    q[i] = math.degrees((raw - backend.offset[i]) * backend.direction[i])
                    lo[i], hi[i] = min(lo[i], q[i]), max(hi[i], q[i])
                    run[i] = 0
                except Exception:  # noqa: BLE001 - motorbridge raises CallError when no answer comes in time
                    q[i] = np.nan
                    missed[i] += 1
                    run[i] += 1
                    longest[i] = max(longest[i], run[i])
            if time.monotonic() - t_print >= 0.5:
                t_print = time.monotonic()
                cells = '  '.join(f'{"--" if np.isnan(a) else f"{a:6.1f}":>6s}' for a in q)
                print(f'{t_print - t0:6.1f} s | {cells} | missed {missed.tolist()}', flush=True)
    except KeyboardInterrupt:
        print()
    finally:
        backend.close(disable=False)
    print('result:')
    for i in range(n):
        seen = 'never answered' if not np.isfinite(lo[i]) else f'angle {lo[i]:.1f} .. {hi[i]:.1f} deg'
        verdict = (
            'OK'
            if missed[i] == 0
            else 'NO ANSWER AT ALL'
            if missed[i] == asked[i]
            else f'DROPS OUT ({longest[i]} in a row at worst)'
        )
        print(
            f'  joint {i + 1} (CAN id {cfg.motors[i].can_id}): {asked[i] - missed[i]} of {asked[i]} answers, {seen}: {verdict}'
        )
    return 0 if not missed.any() else 1


if __name__ == '__main__':
    sys.exit(main())
