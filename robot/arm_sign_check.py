"""Hand-moved sign check of the arm's six joints. Torque stays off the whole time.

    uv run python robot/arm_sign_check.py            # run it in a terminal next to the arm

For each joint in turn the operator moves it a little by hand in the direction the model calls positive; the
script watches the reading and says whether the sign agrees. This is step 1 of the bring-up in
docs/user/hardware-test-plan.md of the rebot-control repository. The result is saved to /tmp/asfinger-arm-sign-check.json.

Directions are given for someone standing behind the arm and looking into the box (x forward, y left, z up).
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from rebot_control import Arm

THRESHOLD = math.radians(8.0)  # a deliberate move, well above anything a resting joint does
RESULT_PATH = '/tmp/asfinger-arm-sign-check.json'

# (joint index, name, how to move it in the model's positive direction)
STEPS = [
    (0, '第 1 轴 底座', '把整个机械臂绕底座转一点，让推杆尖向【右】摆'),
    (1, '第 2 轴 肩', '托住机械臂，把大臂（靠近底座的那一节）从折叠位【抬起来】一点'),
    (2, '第 3 轴 肘', '托住机械臂，把小臂【抬起来 / 张开】一点'),
    (3, '第 4 轴 腕俯仰', '让末端工具【向上翘】（推杆尖抬高）'),
    (4, '第 5 轴 腕偏航', '让末端工具水平转一点，推杆尖向【左】摆'),
    (5, '第 6 轴 腕滚转', '从身后看【逆时针】拧末端工具（手机左边往下、右边往上）'),
]


def wait_still(arm, hold_s: float = 1.0, timeout_s: float = 30.0) -> np.ndarray:
    """Mean joint angles once nothing has moved more than 0.5 deg for `hold_s`."""
    t_end = time.monotonic() + timeout_s
    window = [arm.q()]
    t_window = time.monotonic()
    while time.monotonic() < t_end:
        arm.sleep(0.05)
        q = arm.q()
        if np.abs(q - window[0]).max() > math.radians(0.5):
            window, t_window = [q], time.monotonic()
        else:
            window.append(q)
            if time.monotonic() - t_window >= hold_s:
                break
    return np.mean(window, axis=0)


def main() -> int:
    backend = 'sim' if '--sim' in sys.argv else 'real'
    results: dict[str, str] = {}
    with Arm.from_config(
        'b601_rs',
        tool=str(Path(__file__).resolve().parent.parent / 'calibration/tool_ip17pro_print.yaml'),
        backend=backend,
    ) as arm:
        if arm.taken_over:
            print(
                '电机现在是使能状态，机械臂正被保持着，关节掰不动。请先释放：robot/arm release（先用手托住机械臂）。什么都没有改动。'
            )
            return 3
        print(f'\n已连接，电机保持失能（不出力）。当前关节角 {np.round(np.degrees(arm.q()), 1).tolist()} 度')
        print('每一步按提示用手把对应的轴掰动 10 度左右，看到判定后放回原位。Ctrl-C 可以随时结束。')
        input('准备好后按回车开始 ')
        try:
            for j, name, how in STEPS:
                base = wait_still(arm)
                print(f'\n{name}：{how}')
                t_end = time.monotonic() + 90.0
                verdict = '超时，没有检测到动作'
                while time.monotonic() < t_end:
                    arm.sleep(0.05)
                    d = arm.q() - base
                    others = np.abs(np.delete(d, j)).max()
                    print(
                        f'\r  本轴读数变化 {math.degrees(d[j]):+6.1f} 度   其他轴最大 {math.degrees(others):4.1f} 度   ',
                        end='',
                        flush=True,
                    )
                    if abs(d[j]) > THRESHOLD:
                        verdict = '正方向一致' if d[j] > 0 else '方向相反'
                        break
                print(f'\n  -> {verdict}')
                results[f'joint{j + 1}'] = verdict
                if j != STEPS[-1][0]:
                    print('  请放回原位并松手 ...', end='', flush=True)
                    wait_still(arm, hold_s=1.5)
                    print(' 好')
        except KeyboardInterrupt:
            print('\n提前结束')
        final = np.round(np.degrees(arm.q()), 1).tolist()
    print('\n结果：')
    for k, v in results.items():
        print(f'  {k}: {v}')
    with open(RESULT_PATH, 'w') as f:
        json.dump(
            {'time': time.strftime('%Y-%m-%d %H:%M:%S'), 'backend': backend, 'results': results, 'final_q_deg': final},
            f,
            ensure_ascii=False,
            indent=1,
        )
    print(f'已保存到 {RESULT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
