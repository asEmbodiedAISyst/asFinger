# 数据采集

这一页讲一个 episode 里有什么、怎么录、怎么把录好的 episode 转成 LeRobot 数据集。一个 episode 里有机械臂的伺服日志和两部手机的数据流，时间都换算到同一个时钟上，也就是电脑的时钟。

## 一个 episode 里有什么

每个 episode 是一个目录：`data/episodes/<时间>-<任务名>/`。`data/` 不进 git，因为录下来的数据很大。

| 文件 | 内容 |
| --- | --- |
| `meta.yaml` | 任务名 `task`、任务内的序号 `index`、任务的文字描述 `instruction`、`success`、操作者、起止时间、桌面高度，以及每部手机的设备号和时钟偏移。 |
| `config/` | 录制当时的工具模型、机械臂标定和桌面高度三个文件的副本。以后这些文件改了，旧数据仍然能按当时的模型来读。 |
| `arm.npz` | 150 Hz 的伺服日志：`t`（unix 秒）、`q`、`dq`、`tau`、`temp`、`q_cmd`、`dq_cmd`、`kp`、`kd`、`tau_ff`；还有程序写入的流，每个流 `名字` 的时间在 `名字_t` 里。 |
| `top.mcap`、`wrist.mcap` | 手机发来的原始数据（H.264 视频和 IMU），是 iMuninn 自己的格式，视频没有重新编码。 |

遥操作和直线测试写入的流：

| 流 | 含义 |
| --- | --- |
| `tcp_target` | 指令的工具位姿（机械臂坐标系）：位置 3 个数，加按行展开的旋转矩阵 9 个数。 |
| `q_target` | 指令的关节角（rad）。 |
| `engaged` | 机械臂跟随操作者时为 1。 |
| `limited` | 当前起作用的限制，按位相加：1 倾角界，2 朝向界，4 箱子，8 手机离桌面太近，16 姿态做不到，32 位置做不到。 |
| `leader_pose`、`leader_age`、`leader_heading` | iPhone 遥操作：leader 手机的位姿（位置和四元数 x、y、z、w，AR 世界坐标系）、它的延迟，以及 AR 世界和机械臂坐标系之间的朝向对齐角。 |
| `leader_raw`、`leader_target` | leader 臂遥操作：从 leader 读到的角度（度），和映射到 follower 关节的目标（rad）。 |

### 读一个 episode

```bash
uv run python robot/episode.py list                           # 每个 episode 一行
uv run python robot/episode.py info data/episodes/<名字>       # 帧率、缺帧、时钟偏移
uv run python robot/episode.py sync data/episodes/<名字>       # 视频和关节数据之间的时间差
uv run python robot/episode.py frames data/episodes/<名字> --cam top --every 1 -o <目录>
uv run python robot/episode.py video data/episodes/<名字>      # 每个相机导出一个 mp4
```

在 Python 里，`robot/episode.py` 的 `load(目录)` 返回元数据和伺服日志，`frames(目录, "top")` 逐帧给出画面和它的拍摄时刻。

> **读视频要用 `frames()`。** 不要把解码出来的画面，和刚喂给解码器的那条消息的时间配成一对。解码器的输出要晚好几帧，这样配会错开约 0.27 秒。`frames()` 已经处理了这一点。

在这套设备上，两部手机的画面比关节数据晚 8 到 20 ms，60 fps 下大约一帧。`sync` 可以对一个机械臂动过的 episode 测出这个值。

## 只录制，不控制

```bash
uv run python robot/record.py --task push-cube            # 两部手机加机械臂，机械臂只读
uv run python robot/record.py --task push-cube --no-arm   # 只录手机
```

| 按键 | 作用 |
| --- | --- |
| `r` | 开始一个 episode，再按一次停止并保存。 |
| `f` | 这一条失败了：停止并保存，标成 `success: false`。没在录制时，把刚保存的那一条标成失败。 |
| `x` | 扔掉上一个 episode。它被移到 `data/discarded/`，不会删除。 |
| `q` | 退出。正在录的 episode 会先保存。 |

两个 episode 之间手机保持连接。按下 `r` 就立刻开始录：文件里还带着按键之前最近一个关键帧以来的画面，最多约 1 秒。

`record.py` 不控制机械臂。同一时间只能有一个程序连接机械臂，所以要让机械臂动的程序必须自己负责录制。[遥操作](teleoperation.md)工具就是这样做的，按键也相同。自己写程序时用 `EpisodeRecorder`：

```python
from episode import EpisodeRecorder

with EpisodeRecorder(arm, label='push', cams=('top', 'wrist')) as rec:
    ...
    rec.add('tcp_target', values)  # 额外的流，每调用一次写一行
print(rec.path)
```

## 失败的 episode

| 情况 | 按键 | 结果 |
| --- | --- | --- |
| 任务完成了，中途纠正过也算 | `r` | 正常的 episode。 |
| 任务没有完成 | `f` | 留在 `data/episodes/` 里，标着 `success: false`。转换时默认不带它。 |
| 操作失误，或者录制出了问题 | `x` | 移到 `data/discarded/`。 |

## 转成 LeRobot 数据集

```bash
uv run python robot/to_lerobot.py --task push-line --plan     # 只列出会转哪些
uv run python robot/to_lerobot.py --task push-line --crop top=1000,170,640,640    # 写到 data/lerobot/push-line
uv run python robot/to_lerobot.py --task push-line --instruction "push the black cube along the black line to the other end" --overwrite
```

输出是 v2.1 格式的 LeRobot 数据集：每个 episode、每个相机各一个 parquet 文件和一个 mp4，外加 `meta/` 里的几张表。文件由工具直接写出，不需要安装 lerobot。原始 episode 不会被改动，数据集可以随时删掉重转。

工具会转这个任务下所有完整的、不是仿真的、没有标成失败的 episode，按录制顺序编号。`--include-failed` 和 `--include-sim` 可以把另外两类也带上。

每个 episode 按固定的 `--fps`（默认 30）重新取样。每一帧包含：

| 列 | 内容 |
| --- | --- |
| `observation.images.top`、`observation.images.wrist` | 拍摄时刻离这一帧最近的画面。给了 `--crop` 就先裁，再缩放到 `--height`（默认 480）。视频编码是 H.264，`--vcodec libsvtav1` 换成 AV1。 |
| `observation.state` | 这一时刻的六个关节角（rad），由伺服日志插值得到。 |
| `action` | 遥操作在这一时刻发出的关节目标（rad）。是绝对值，不是增量。录像里没有这个流时，`--action next-state` 用下一帧的关节角。 |
| `observation.tcp_pose`、`action.tcp_pose` | 杆尖的实测位姿和指令位姿，各 9 个数：x、y、z（m），加旋转矩阵的前两列。 |
| `timestamp`、`frame_index`、`episode_index`、`index`、`task_index` | LeRobot 自己的列。 |

- 任务文字取 episode 的 `instruction`，`--instruction` 可以在转换时整体换掉。
- 遥操作的录像会切掉第一次接合之前和最后一次脱开之后的部分，`--keep-idle` 保留它们。
- `meta/source_episodes.jsonl` 记着数据集里每个 episode 来自哪个录像、切掉了多少；`meta/conversion.json` 记着这次转换的选项，包括裁剪框。
- 关节角比 `action` 晚约 60 到 80 ms，这是机械臂跟随指令的滞后。

### 裁剪俯视画面

顶部相机拍到的是整个箱子，白板只占画面的 7 % 左右。缩成小图以后，白板上的一条细线连一个像素都不到。

`--crop 相机=x,y,宽,高` 在缩放之前先从画面里裁出一块，数值是录下来的画面的像素，从左上角算起。和 `--plan` 一起用时，工具会把第一个、中间一个和最后一个 episode 的第一帧画上裁剪框，存在数据集目录旁边。看一下这几张图，确认所有 episode 里要看的东西都在框内。以后把实时画面喂给用这个数据集做出来的东西时，要按同一个框裁。

### 用 lerobot 检查数据集

```bash
python robot/check_lerobot.py data/lerobot/push-line
```

要用装了 lerobot（数据集格式 v2.1）的 Python 环境运行，`robot` 依赖组里没有 lerobot。工具从目录加载数据集，解码每个 episode 的画面，并组出一个 batch。
