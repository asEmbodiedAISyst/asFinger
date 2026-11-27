# 遥操作

有两个工具可以让操作者带着机械臂动，同时录制 episode：一个用手持的 iPhone，一个用 leader 臂。操作者手里的设备叫 leader，机械臂这一端叫 follower。

[机械臂工具与安全规则](robot-arm-tools.md)里的规则在这里同样适用：用真机时要有人守着电机的电源开关。

## 两个工具的共同行为

两个工具共用机械臂这一侧的逻辑（`robot/teleop.py`）：

- 机械臂从折叠位或 home 位开始，展开到工具的 home 位后等待。**只有接合以后，它才跟随操作者。**
- 不加 `--yes` 时只打印计划，什么都不动。
- 机械臂出故障（堵转、过温、总线断开）时原地保持，用 `robot/arm release` 结束。
- leader 的数据过期或者发生跳变时，工具自动脱开，机械臂保持不动。

| 按键 | 作用 |
| --- | --- |
| 空格 | 接合或脱开。 |
| `r` | 开始一个 episode，再按一次停止并保存。 |
| `f` | 这一条失败了：停止并保存，标成 `success: false`。没在录制时，把刚保存的那一条标成失败。 |
| `x` | 扔掉上一个 episode（移到 `data/discarded/`）。 |
| `h` | 脱开并回到 home 位。 |
| `q` | 退出：回 home、折叠、断力矩。 |

按键之后不用回车。

### 工具能走多远

工具可以一直走到硬件允许的地方。挡住它的是几何条件，不是固定的角度：

- 关节限位；
- 箱子：各关节中心、杆尖和工具上的手机都要在 `calibration/workspace.yaml` 的范围里，杆尖不高于 `--z-max`（默认 0.35 m）；
- 桌面：杆尖至少高出 `--z-min`（默认 10 mm），手机至少高出 `--phone-clear`（默认 15 mm）；
- 机械臂自身：手机和推杆离底座立柱、大臂、小臂的中心线至少 `--arm-clear`（默认 7 cm）。连杆的外形不在模型里，这个距离是估的。

**位置优先。** 指令的姿态做不到时，工具保持现有姿态，位置继续跟随；只有位置本身够不到时才停。状态行会写出当前是哪一项在限制，`limited` 流里也录着同样的信息。

速度上限是 `--max-speed`（默认 0.15 m/s）、`--max-turn`（默认 60 deg/s）和 `--max-joint-speed`（默认 60 deg/s）。

推杆能倾斜多少由关节限位决定，所以和方向有关。按模型算，杆尖在 (0.30, 0, 0.05) m 时：朝前约 46°，朝左右各约 78°，朝底座方向约 32°。

## 用 iPhone

```bash
uv run imuninn list                                    # 找到手持手机的名字或地址
uv run imuninn profile apply teleop <地址>              # 切到 AR 模式并打开位姿流
uv run python robot/teleop_iphone.py --leader <名字或地址> --task push-cube          # 只打印计划
uv run python robot/teleop_iphone.py --leader <名字或地址> --task push-cube --yes
uv run python robot/teleop_iphone.py --sim --keys "1:space,3:r,14:r,15:q"            # 仿真，脚本化的手
```

手持的手机映射到工具上的手机。设想是：leader 相当于握在手里的另一根推杆，手机装在同样的位置上，那么手机对上了，杆尖也就对上了。

- **姿态是绝对映射。** 工具上的手机取手持手机的姿态。横滚和俯仰靠重力对齐，是绝对的；朝向没有公共基准，所以在第一次接合时对齐。脱开时按 `y` 可以重新对齐。
- **位置是相对映射。** 接合期间，工具上的手机移动的量，等于手持手机从接合那一刻起的位移乘以 `--scale`。手伸到头了就脱开，把手收回来，再接合。
- **接合前先把 leader 拿成和 follower 差不多的姿态。** 状态行显示两者的姿态相差多少度。超过 `--max-engage-angle`（默认 10°）时拒绝接合；剩下的差以 `--catch-up-turn`（默认 20 deg/s）慢慢追上。
- `--point tip` 改成让杆尖跟随 leader 的平移，这时只转动手机，杆尖不动。

这个工具在真机上用过。上面讲的接合条件和范围限制是在那之后改的，这些改动只在仿真里测过。

## 用 leader 臂

```bash
uv run python robot/teleop_star.py --check       # leader 和机械臂的角度并排显示，什么都不动
uv run python robot/teleop_star.py               # 只打印计划
uv run python robot/teleop_star.py --yes
uv run python robot/teleop_star.py --set-zero    # 把 leader 当前的姿态写进舵机，作为零点
uv run python robot/teleop_star.py --sim --fake --keys "1:space,3:r,12:r,13:q"    # 仿真，脚本化的 leader
```

leader 是一台 Star Arm 102。读取方式和官方给 LeRobot 做的 reBot 支持相同：Fashion Star 总线舵机，编号 0–5 对应关节 1–6，USB 串口 1 Mbit/s，通过 `motorbridge-smart-servo` 包读取。映射是关节对关节：

```text
follower 关节角 = 符号 × leader 角度 + 偏移      符号 (+1, +1, −1, −1, −1, +1)，偏移 0
```

串口、编号、符号、偏移和范围都在 `calibration/star_leader.yaml` 里。

1. 接上 leader。在 Linux 上串口会出现为 `/dev/ttyUSB0`，当前用户要在 `dialout` 组里。
2. 把 leader 折成零位（对应机械臂的折叠位），运行 `--set-zero`。这一步会永久写入舵机。
3. 机械臂折叠、leader 折叠时运行 `--check`，六行都应该接近 0。逐个扳动 leader 的关节，看映射后的值是不是朝 follower 对应关节的正方向变化。不是的话，改文件里的符号或偏移。
4. 遥操作。把 leader 摆成和机械臂差不多的姿态，所有关节相差不超过 `--max-engage-diff`（默认 15°）才能接合。

> **没有在真实硬件上验证过。** 这个工具只在仿真里用脚本化的 leader 测过。符号和零点是照官方代码写的，没有用真实的 leader 臂在这台机械臂上核对。先做第 3 步，再做第 4 步。
