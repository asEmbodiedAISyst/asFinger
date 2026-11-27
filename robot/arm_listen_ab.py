"""Blind listening test: does a setting change how loud the motors are while the arm holds still?

    uv run python robot/arm_listen_ab.py kp             # real arm: operator at the power switch
    uv run python robot/arm_listen_ab.py kp --sim

One continuous hold at the current pose, in four 8 s segments: two with setting A and two with setting B, in a
random order that is saved next to the log and not printed. Note for each segment whether the motors sound loud
or quiet, then compare with the saved order.

What can be compared (A is always the current calibration, calibration/b601_rs.yaml):
    kp        B: kp halved on shoulder and elbow
    soft      B: kp halved and kd x 0.7 on shoulder and elbow (same damping ratio as A)
    wrist-kd  B: kd halved on the three wrist joints
    filter    B: velocity filter gain of the elbow motor 0.05 instead of 0.1 (RobStride parameter 0x7021, RAM only)

Also records the servo log and the wrist phone's accelerometer. At the end everything is back at A and torque
goes off without folding, so start it with torque off and the arm in a pose it can rest in. If the run fails in
an unexpected way, the arm holds where it is and stays enabled (the library's rule); end that with
`rebot-control release`.
"""

import json, math, os, random, signal, sys, threading, time
import numpy as np
from rebot_control import Arm


def _term(*_):
    raise KeyboardInterrupt


signal.signal(signal.SIGTERM, _term)
sim = '--sim' in sys.argv
VARIANTS = ('kp', 'soft', 'wrist-kd', 'filter')
variant = next((a for a in sys.argv[1:] if not a.startswith('--')), None)
if variant not in VARIANTS:
    sys.exit(f'usage: arm_listen_ab.py {{{"|".join(VARIANTS)}}} [--sim]')
os.makedirs('calibration/data', exist_ok=True)
out = time.strftime(f'calibration/data/listen-{variant}-%Y%m%d-%H%M%S') + ('-sim' if sim else '') + '.npz'
SEG, PARAM = 8.0, 0x7021
order = random.choice(['ABAB', 'BABA', 'ABBA', 'BAAB'])

acc, stop = [], threading.Event()


def imu_thread():
    try:
        import imuninn
        from snapshot import camera

        with imuninn.connect(camera('wrist')[0]) as dev:
            dev.start()  # the IMU only streams while the capture session runs
            for s in dev.iter('imu', timeout=5.0):
                acc.append((time.perf_counter(), s.accel.x, s.accel.y, s.accel.z))
                if stop.is_set():
                    break
            dev.stop()
    except Exception as e:
        print('wrist IMU not recorded:', type(e).__name__, e, flush=True)


if not sim:
    threading.Thread(target=imu_thread, daemon=True).start()


def apply(arm, which, kp0, kd0):
    """Switch to setting A or B of the chosen variant."""
    kp, kd, filt = kp0.copy(), kd0.copy(), 0.1
    if which == 'B':
        if variant in ('kp', 'soft'):
            kp[[1, 2]] *= 0.5
        if variant == 'soft':
            kd[[1, 2]] *= 0.7
        if variant == 'wrist-kd':
            kd[[3, 4, 5]] *= 0.5
        if variant == 'filter':
            filt = 0.05
    arm.set_gains(kp, kd)
    if variant == 'filter' and not sim:
        with arm.backend._lock:
            arm.backend.motors[2].robstride_write_param_f32(PARAM, filt)


with Arm.from_config(
    'b601_rs',
    tool='calibration/tool_ip17pro_print.yaml',
    calibration='calibration/b601_rs.yaml',
    backend='sim' if sim else 'real',
) as arm:
    if arm.taken_over:
        sys.exit(
            'The motors are already enabled and holding the arm. This tool only starts from torque off: end the '
            'hold first with `rebot-control release` (hand on the arm). Nothing was changed.'
        )
    q0 = arm.q().copy()
    marks = []
    kp0, kd0 = arm.servo.kp.copy(), arm.servo.kd.copy()
    print(
        f"comparing '{variant}'; A: kp {kp0.tolist()} kd {kd0.tolist()}; torque on, then 4 segments of {SEG:g} s",
        flush=True,
    )
    try:
        apply(arm, order[0], kp0, kd0)
        arm.enable()
        arm.start_recording()
        for k, which in enumerate(order):
            apply(arm, which, kp0, kd0)
            marks.append(arm.now())
            print(f'--- segment {k + 1} of 4 ---', flush=True)
            t_end = arm.now() + SEG
            while arm.now() < t_end:
                arm.wait(1.0)
                st = arm.state()
                if np.abs(st.q - q0).max() > math.radians(3.0) or st.temp.max() > 60:
                    raise RuntimeError('moved more than 3 deg or too hot')
        marks.append(arm.now())
    except KeyboardInterrupt:
        print('interrupted', flush=True)
    rec = arm.stop_recording()
    arm.disable_torque()  # the run started from a rest pose
    apply(arm, 'A', kp0, kd0)
    print('torque off (no fold); settings back at A', flush=True)
stop.set()
time.sleep(0.3)
np.savez(out, marks=np.array(marks), order=np.array(list(order)), acc=np.array(acc) if acc else np.zeros((0, 4)), **rec)
json.dump({'variant': variant, 'order': order}, open(out + '.order.json', 'w'))
print(
    f'saved {out} ({len(rec["t"])} servo samples, {len(acc)} IMU samples); the order is in {out}.order.json', flush=True
)
