# 真机环境

这一页说明 `robot/` 里的脚本需要什么样的硬件，以及软件怎么安装和配置。这些脚本控制一台装着本项目推杆的机械臂，并从两部手机采集数据。

> **现状。** `robot/`、`calibration/` 和 `sim/` 里的代码是从这套设备原来的工作仓库搬过来的，还没有从本仓库在真机上运行过。在本仓库里只做了仿真测试。

真实设备的照片以后补上。

## 设备组成

| 部件 | 说明 |
| --- | --- |
| 机械臂 | Seeed reBot Arm B601-RS：6 个 RobStride 电机，挂在一条 CAN 总线上。 |
| 工具 | 本项目打印出来的推杆，上面装一部 iPhone 17 Pro。给控制库用的工具模型是 `calibration/tool_ip17pro_print.yaml`。 |
| 腕部相机 | 工具上的那部手机，跟着机械臂运动。 |
| 顶部相机 | 另一部手机，固定在工作区上方，斜着往下看，能看到整个工作区。 |
| 工作区 | 罩住机械臂的摄影箱（边长 80 cm 的立方体，正面开口），桌面是一块白板。 |
| 标记 | 白板上的 AprilTag 36h11 标记和一张色卡，见[标定](robot-calibration.md#标记)。 |
| 电脑 | 控制真机要一台带 CAN 适配器的 Linux 电脑。仿真在 macOS 上也能跑。 |

两部手机都运行 [iMuninn](https://imuninn.projects.weijinqi.com) app，电脑用 Python 包 `imuninn` 连接它们。

机械臂通过 [rebot-control](https://github.com/asEmbodiedAISyst/rebot-control) 控制。使用真机之前，先读它的安全说明。

## 机械臂坐标系

脚本和标定文件里的位置都在机械臂的底座坐标系里：原点在底座中心的安装面上，X 朝前指向箱子里面，Y 朝左（站在机械臂身后看），Z 朝上。长度单位是米。

## 安装

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
uv sync --group robot --python 3.12
```

依赖组 `robot` 里是这些脚本要导入的东西：rebot-control 和它的仿真器、imuninn、OpenCV、PyAV、pyarrow，以及几个小包。`asfinger` 包本身不需要这个组。

- rebot-control 不在 PyPI 上，`pyproject.toml` 从 GitHub 取它的一个固定提交。
- 这个组是在 Python 3.12 上测试的。rebot-control 依赖的 Pinocchio 不会马上支持最新的 Python 版本。
- 电机驱动 `motorbridge` 只在 Linux 上安装。在 macOS 上，带 `--sim` 的功能都能用。

脚本在仓库根目录下运行：

```bash
uv run python robot/arm_move.py --help
```

## CAN 总线

电机接在 SocketCAN 接口 `can0` 上，波特率 1 Mbit/s。电脑重启或者适配器重新插拔之后，接口是关着的，要先拉起来：

```bash
sudo ip link set can0 type can bitrate 1000000 restart-ms 100 && sudo ip link set can0 up
```

同一时间只能有一个程序连接机械臂，第二个会报错退出。

## 手机

把手机和电脑接到同一个局域网里，然后告诉脚本手机在哪：

1. 把 `robot/cameras.example.yaml` 复制成 `robot/cameras.local.yaml`。git 会忽略这个副本，手机地址只留在你自己的电脑上。
2. 用 `uv run imuninn list` 找到每部手机，把地址或 iMuninn 名称填进文件。
3. 运行 `uv run python robot/snapshot.py --cam top`。工具会给出一条警告，里面有实际应答的那部手机的设备号，把它抄进文件。`--cam wrist` 同样做一遍。

| 字段 | 含义 |
| --- | --- |
| `address` | 手机的地址或 iMuninn 名称。环境变量 `ASFINGER_TOP_CAM`、`ASFINGER_WRIST_CAM` 可以临时替换它；旧名字 `IPUSH_TOP_CAM`、`IPUSH_WRIST_CAM` 仍然有效。 |
| `device_id` | 手机上报的设备号。连到的不是这部手机时，工具会给出警告。 |
| `label` | 你给这部手机起的名字，只出现在提示信息里。 |

没有 `robot/cameras.local.yaml` 时，需要手机的工具会给出提示并停下。

### 相机配置

每部手机的配置是一个 profile 文件：

| Profile | 镜头和格式 | 曝光和白平衡 |
| --- | --- | --- |
| `robot/top_camera.yaml` | 超广角，1920 × 1440，60 fps | 手动。这样不同时间拍的画面可以直接比较。 |
| `robot/wrist_camera.yaml` | 超广角，640 × 480，60 fps | 自动。机械臂一动，画面内容就变了。 |

超广角镜头在各个 4:3 格式下视场角相同，约 103° × 86°。腕部相机用小格式，是因为存储占用小、解码快。

iMuninn 重启后，手机会回到默认配置。工具会把手机的当前配置和 profile 对比，不一致时给出警告，并附上恢复用的命令：

```bash
uv run imuninn profile apply robot/top_camera.yaml <顶部手机的地址>
```

顶部相机的手动曝光和白平衡是用 `robot/calibrate_color.py` 对着色卡找出来的，灯光变了要重做，见[标定](robot-calibration.md#色卡)。

### 看一眼工作区

```bash
uv run python robot/snapshot.py -o top.jpg                 # 顶部相机
uv run python robot/snapshot.py --cam wrist -o wrist.jpg   # 腕部相机
uv run python robot/tags.py top.jpg                        # 图里的标记：ID、边长、中心、四个角
```

- 手机的采集会话没开时，`snapshot.py` 会自己打开，拍完再关掉。要连拍就加 `--keep-running`。
- 图片按传感器方向保存，相机内参和标记检测用的是同一个方向。
- `snapshot.py` 不会改动手机的配置。

采集会话是手机上的状态，连接断开后依然保持。只关你自己打开的会话，因为别的程序可能正在用同一部手机。

## 限制

- **顶部相机是斜着看的。** 同样大的东西，靠近机械臂时在画面里比在相机正下方小得多。不要把像素距离直接当比例尺，要用桌面上的标记来换算。
- **没有镜头模型。** 手机不提供畸变系数。在白板范围内，用顶部相机量长度的误差约 1 %；腕部相机在画面角落的误差到过 8 %。
- **小标记。** 640 × 480 下，腕部相机在 35 cm 外能稳定检出 50 mm 的标记，同样距离上 30 mm 的标记不可靠。
- **检查知道的不多。** 脚本做越界检查时只用到各关节中心、杆尖和工具上的手机，不知道连杆的外形、线缆和桌上的东西。
