# Data collection

This page describes what an episode contains, how to record one, and how to convert recorded episodes into a LeRobot dataset. An episode holds the servo log of the arm and the streams of both phones on one clock, the clock of the computer.

## What an episode contains

Each episode is one folder, `data/episodes/<time>-<task>/`. The folder `data/` is not in git, because the recordings are large.

| File | Content |
| --- | --- |
| `meta.yaml` | The task name `task`, the number `index` inside the task, the task in words `instruction`, `success`, the operator, start and end time, the table height, and for each phone its device id and clock offset. |
| `config/` | Copies of the tool model, the arm calibration and the table height as they were at the time of the recording. Old data stays readable when these files change later. |
| `arm.npz` | The servo log at 150 Hz: `t` (unix seconds), `q`, `dq`, `tau`, `temp`, `q_cmd`, `dq_cmd`, `kp`, `kd`, `tau_ff`. Also the streams that the program wrote: each stream `name` has its times in `name_t`. |
| `top.mcap`, `wrist.mcap` | The raw data of the phones (H.264 video and IMU) in the format of iMuninn. The video is not encoded again. |

Streams that teleoperation and the line test write:

| Stream | Meaning |
| --- | --- |
| `tcp_target` | The commanded tool pose in the arm frame: the position (3 numbers) and the rotation matrix by rows (9 numbers). |
| `q_target` | The commanded joint angles (rad). |
| `engaged` | 1 while the arm follows the operator. |
| `limited` | Which limit is active, as a sum: 1 tilt bound, 2 heading bound, 4 box, 8 phone too near the table, 16 orientation not reachable, 32 position not reachable. |
| `leader_pose`, `leader_age`, `leader_heading` | iPhone teleoperation: the pose of the leader phone (position and quaternion x, y, z, w in the AR world frame), its delay, and the heading alignment between the AR world and the arm frame. |
| `leader_raw`, `leader_target` | Leader-arm teleoperation: the angles read from the leader (deg) and the targets mapped to the follower joints (rad). |

### Read an episode

```bash
uv run python robot/episode.py list                           # one line for each episode
uv run python robot/episode.py info data/episodes/<name>      # rates, gaps, clock offsets
uv run python robot/episode.py sync data/episodes/<name>      # time offset between video and joint data
uv run python robot/episode.py frames data/episodes/<name> --cam top --every 1 -o <folder>
uv run python robot/episode.py video data/episodes/<name>     # one mp4 for each camera
```

In Python, `load(folder)` in `robot/episode.py` returns the metadata and the servo log, and `frames(folder, "top")` gives each picture with its capture time.

> **Use `frames()` to read video.** Do not pair a decoded picture with the time of the message that you just gave to the decoder. The decoder gives pictures out several frames late, so the pair is wrong by about 0.27 s. `frames()` handles this.

In this setup the pictures of both phones are 8 to 20 ms later than the joint data, about one frame at 60 fps. `sync` measures this for an episode in which the arm moves.

## Record without control

```bash
uv run python robot/record.py --task push-cube            # both phones and the arm; the arm is only read
uv run python robot/record.py --task push-cube --no-arm   # phones only
```

| Key | Function |
| --- | --- |
| `r` | Start an episode. Press again to stop and save it. |
| `f` | The episode failed: stop and save it with `success: false`. When nothing is recording, mark the last saved episode as failed. |
| `x` | Throw the last episode away. It moves to `data/discarded/` and is not deleted. |
| `q` | Quit. An episode that is recording is saved first. |

The phones stay connected between episodes. A recording starts at once when you press `r`: the file also holds the pictures since the last keyframe before the key, up to about 1 s.

`record.py` does not control the arm. Only one program can be connected to the arm, so a program that moves the arm must record by itself. The [teleoperation](teleoperation.md) tools do this with the same keys. In your own program, use `EpisodeRecorder`:

```python
from episode import EpisodeRecorder

with EpisodeRecorder(arm, label='push', cams=('top', 'wrist')) as rec:
    ...
    rec.add('tcp_target', values)  # an extra stream, one row for each call
print(rec.path)
```

## Episodes that failed

| Case | Key | Result |
| --- | --- | --- |
| The task was completed, also after a correction on the way | `r` | A normal episode. |
| The task was not completed | `f` | Kept in `data/episodes/` with `success: false`. The conversion leaves it out by default. |
| A mistake of the operator, or the recording went wrong | `x` | Moved to `data/discarded/`. |

## Convert to a LeRobot dataset

```bash
uv run python robot/to_lerobot.py --task push-line --plan     # list what would be converted
uv run python robot/to_lerobot.py --task push-line --crop top=1000,170,640,640    # write data/lerobot/push-line
uv run python robot/to_lerobot.py --task push-line --instruction "push the black cube along the black line to the other end" --overwrite
```

The output is a LeRobot dataset in the format v2.1: one parquet file and one mp4 for each camera and episode, and the tables in `meta/`. The tool writes the files directly and does not need lerobot. The raw episodes do not change, so you can delete a dataset and make it again.

The tool takes all episodes of the task that are complete, not from the simulator and not marked as failed, in the order of recording. `--include-failed` and `--include-sim` add the others.

Each episode is sampled again at a fixed `--fps` (default 30). One frame holds:

| Column | Content |
| --- | --- |
| `observation.images.top`, `observation.images.wrist` | The picture with the capture time nearest to the frame. It is cut with `--crop` if given, then scaled to `--height` (default 480). The video codec is H.264; `--vcodec libsvtav1` selects AV1. |
| `observation.state` | The six joint angles (rad) at this time, interpolated from the servo log. |
| `action` | The joint target (rad) that teleoperation sent at this time. It is absolute, not a difference. For a recording without that stream, `--action next-state` uses the joint angles of the next frame. |
| `observation.tcp_pose`, `action.tcp_pose` | The measured and the commanded pose of the tip, 9 numbers each: x, y, z (m) and the first two columns of the rotation matrix. |
| `timestamp`, `frame_index`, `episode_index`, `index`, `task_index` | The columns of LeRobot. |

- The task text is the `instruction` of the episode. `--instruction` replaces it for all episodes.
- For a teleoperated recording, the tool cuts the part before the first engaged moment and after the last one. `--keep-idle` keeps them.
- `meta/source_episodes.jsonl` says which recording each episode of the dataset comes from, and how much was cut. `meta/conversion.json` holds the options of the run, the crop among them.
- The joint angles follow `action` by about 60 to 80 ms. This is the lag of the arm behind its command.

### Crop the top view

The top camera sees the whole box. The whiteboard is only about 7 % of the picture. After scaling to a small picture, a thin line on the board is less than one pixel wide.

`--crop CAM=x,y,w,h` cuts a rectangle out of the pictures of a camera before scaling. The values are pixels of the recorded picture, from the top left corner. With `--plan`, the tool saves the first picture of the first, the middle and the last episode with the rectangle drawn in, next to the dataset folder. Look at them to confirm that the rectangle holds the scene in all episodes. Use the same rectangle when you later feed live pictures to something that was made from the dataset.

### Check a dataset with lerobot

```bash
python robot/check_lerobot.py data/lerobot/push-line
```

Run this with a Python environment that has lerobot at the dataset format v2.1. The group `robot` does not contain lerobot. The tool loads the dataset from the folder, decodes pictures of each episode and builds one batch.
