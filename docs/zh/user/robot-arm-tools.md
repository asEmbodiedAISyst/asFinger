# 机械臂工具与安全规则

`robot/` 里的脚本会让真实的机械臂动起来。这一页讲使用规则、程序出错时机械臂的表现，以及每个工具是做什么的。

> **现状。** 这些工具是从这套设备原来的工作仓库搬过来的，还没有从本仓库在真机上运行过。每个工具都先加 `--sim` 跑一遍。

## 规则

- 真机只在有人守在旁边、手在电机电源开关上时才用。
- 任何会上力矩、让机械臂运动或者断力矩的命令，执行前先说清楚会发生什么、最坏会怎样，等操作者同意。
- 新的动作先在仿真里试（`--sim`）。
- 不要放宽控制库里的任何安全限制。
- 打印的推杆受不了大力。需要推杆去碰东西时，碰没碰到由操作者说了算，程序里的检测只是保险。

控制库的安全模型写在 [rebot-control](https://github.com/asEmbodiedAISyst/rebot-control) 的文档里（`docs/user/safety.md`），在这里同样适用。

## 出错时机械臂怎么表现

力矩只在有意的时候才断。

| 情况 | 机械臂的表现 |
| --- | --- |
| 程序正常结束 | 分段折叠回零位，然后断力矩。 |
| 程序出错、被 Ctrl-C 或被杀掉，电脑死机，CAN 线脱落 | 停在原地保持。电机仍然使能，程序退出以后也一直保持。 |
| 控制库检测到堵转 | 原地保持，仍然使能。 |
| 电机驱动过热（超过 125 °C） | 断力矩，机械臂会落下来。这是唯一会自动断力矩的情况。 |
| 操作者运行释放命令 | 断力矩。 |

留在保持状态的机械臂没有任何程序看着：没有堵转检查，也没有温度检查，电机一直在出力，保持久了驱动会发热。用下面的命令结束这个状态：

```bash
robot/arm state              # 现在是不是使能保持着？这条命令什么都不改。
robot/arm release --fold     # 从当前位置折叠回零位，再断力矩
robot/arm release            # 立刻断力矩：先用手托住机械臂
```

`robot/arm` 就是 rebot-control 的命令行，只是自动带上了这台机械臂的工具模型和标定文件，rebot-control 的其他命令也都能这样用。有 `.venv/bin/rebot-control` 时它用这个程序，没有就用 `uv run --group robot rebot-control`。

下一个程序连接时如果发现电机在使能状态，会不带跳变地接过保持，再从那里继续。

## 工具一览

除了表里注明的两个，每个工具加 `--help` 都会打印用法。在真机上，会让机械臂运动的工具不加 `--yes` 时只打印计划，什么都不动。

| 工具 | 作用 |
| --- | --- |
| `arm` | 这台机械臂的 rebot-control 命令行：`robot/arm state`、`robot/arm release`。 |
| `arm_sign_check.py` | 手动符号检查，全程不上力矩。操作者依次掰动每个关节，工具判断方向和模型是否一致。它没有任何选项，一启动就连接机械臂。 |
| `arm_bus_check.py` | 只读。反复向每个电机要角度并统计应答，用来找接触不良的线或插头。 |
| `arm_hold.py` | 在当前姿态上力矩保持，记录电机数据，然后断力矩，不做别的动作。 |
| `arm_move.py` | 按一串关节角路点慢速运动。动之前先检查每个路点和路径有没有越出箱子。 |
| `arm_step_check.py` | 在 home 位让指定关节做一个小阶跃，报告过冲、上升时间和调节时间。改了 `kp`、`kd` 之后用。 |
| `arm_line_test.py` | 让杆尖在桌面上方走直线，把这次运行录成一个 episode，并报告偏差。 |
| `arm_listen_ab.py` | 盲听测试：保持不动时，某项设置会不会改变电机的声音大小？参数是变体的名字，可以再加 `--sim`；它没有 `--help`，一启动就连接机械臂。 |
| `arm_touch_table.py`、`arm_calib_gravity.py`、`arm_calib_ripple.py` | 标定工具，见[标定](robot-calibration.md)。 |
| `teleop_iphone.py`、`teleop_star.py` | 遥操作，见[遥操作](teleoperation.md)。 |
| `record.py`、`episode.py`、`to_lerobot.py`、`check_lerobot.py` | 录制和导出，见[数据采集](data-collection.md)。 |
| `snapshot.py`、`tags.py`、`make_tags.py`、`calibrate_color.py` | 相机和标记，见[真机环境](robot-setup.md)和[标定](robot-calibration.md#标记)。 |

### 慢速关节运动

```bash
uv run python robot/arm_move.py --waypoints "0,=,=,=,0,0; 0,15,20,=,0,0; 0,s,s,=,0,0" --sim
```

一个路点是 6 个关节角，单位是度。`=` 表示这个关节保持上一个路点的角度，`s` 表示程序启动时它所在的角度。计划越出 `calibration/workspace.yaml` 的箱子范围时，工具拒绝执行。

`--end` 决定走完最后一个路点之后做什么：

| 取值 | 结果 |
| --- | --- |
| `hold`（默认） | 停在最后一个路点继续保持，之后用 `robot/arm release` 结束。 |
| `off` | 在最后一个路点断力矩。只能用在机械臂自己能搁住的姿态。 |
| `fold` | 折叠回零位，再断力矩。 |

### 保持测试

```bash
uv run python robot/arm_hold.py --sim
uv run python robot/arm_hold.py --seconds 60 --record hold.npz
```

从断力矩、机械臂搁在折叠位的状态开始。任何关节移动超过 3°，或者驱动温度超过 60 °C，工具就停下并断力矩。和 `rebot-control hold` 不同，它结束时不会折叠机械臂。

### 直线测试

```bash
uv run python robot/arm_line_test.py            # 只打印计划
uv run python robot/arm_line_test.py --yes      # 在真机上执行，约 2 分钟
uv run python robot/arm_line_test.py --sim
uv run python robot/arm_line_test.py --from-data data/episodes/<名字>   # 重新出报告
```

推杆竖直，工具姿态不变。默认路线是在桌面上方 6 cm 处走一组直线，3、6、10 cm/s 各一遍；再在桌面上方 2 cm 处走一条线，3 和 6 cm/s 各一遍。路线下面的桌面必须是空的。

报告对每条线给出：杆尖偏离理想直线多少（横向和高度）、落后指令多远、推杆的倾角、停下后的误差。这些数是按电机上报的关节角算的，是机械臂自己的视角，不代表杆尖在房间里的真实位置。

工具低于桌面上方 8 mm，或者杆尖离指令位置超过 1.5 cm 时，测试中止：停下、抬起工具、折叠机械臂。

## home 位和工具

- 工具的 home 位是推杆竖直、杆尖在 (0.24, 0, 0.12) m，关节角 [0, 71.4, 68.9, −57.6, 0, 0]°。
- 工具模型是 `calibration/tool_ip17pro_print.yaml`：工具原点在推杆末端，Z 轴沿着推杆。`robot/` 里的工具和仿真默认加载它。
- 控制库里有一个叫 `pusher_ip17` 的工具，描述的是更早的设计。直接调用 `rebot-control` 或 `Arm.from_config` 时，要自己传工具文件和 `--calibration calibration/b601_rs.yaml`。

## 需要知道的事

- **`rebot-control hold` 和 `home` 结束时会折叠机械臂。** 只想原地保持的话，用 `robot/arm_hold.py`。
- **断力矩不等于“原地不动”。** 断力矩后关节是松的。工具对第 6 轴不平衡，手机那一侧会垂下去，工具滚转约 80°。每次上力矩之前都要重新读第 6 轴的角度。
- **桌面不在 z = 0。** 按这套设备的标定，桌面在机械臂坐标系里是 z = +20 mm（`calibration/table.yaml`）。杆尖是半径 7.5 mm 的球。
- **滞后不等于接触。** 慢速运动时，杆尖相对目标在超前约 2 mm 到落后约 5 mm 之间变化。不要把几毫米的滞后当成碰到东西的证据。
- **电机不再应答时。** 没有新反馈时，控制库沿用电机上一次的反馈，所以断线看起来像是约一秒之后发生的堵转。要找接触不良的插头，先断力矩，再一边用手摆动机械臂一边运行 `robot/arm_bus_check.py`。
- **`arm_touch_table.py` 和 `arm_sign_check.py` 给操作者的提示是中文的。**
- **`arm_listen_ab.py kp` 和 `soft` 会报错退出。** 用本仓库的标定文件时，控制库因为力矩波动模型而拒绝减半后的 `kp`。`wrist-kd` 和 `filter` 两个变体可以运行。
- **仿真看不出机械臂会不会撞。** 场景里只有推杆参与碰撞，接触参数也是暂估的，见[仿真](simulation.md)。
