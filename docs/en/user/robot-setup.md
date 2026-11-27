# The robot setup

This page describes the hardware that the scripts in `robot/` expect, and how to install and configure the software for it. The scripts drive one arm with the pusher of this project and record data from two phones.

> **Status.** The code in `robot/`, `calibration/` and `sim/` was moved here from the working repository of the setup. It has not been run on the real arm from this repository yet. In this repository it is tested in the simulator only.

Pictures of the real setup will be added later.

## What the setup consists of

| Part | Description |
| --- | --- |
| Arm | Seeed reBot Arm B601-RS: six RobStride motors on one CAN bus. |
| Tool | The printed pusher of this project with an iPhone 17 Pro on it. Its model for the control library is `calibration/tool_ip17pro_print.yaml`. |
| Wrist camera | The phone on the tool. It moves with the arm. |
| Top camera | A second phone, fixed above the workspace. It looks down at an angle and sees the whole workspace. |
| Workspace | A photo box around the arm (a cube with 80 cm sides and an open front), with a whiteboard as the table. |
| Markers | AprilTag 36h11 markers on the whiteboard and a colour card. See [Calibration](robot-calibration.md#markers). |
| Computer | A Linux computer with a CAN adapter for the real arm. The simulator also runs on macOS. |

Both phones run the [iMuninn](https://imuninn.projects.weijinqi.com) app. The computer connects to them with the `imuninn` Python package.

The arm is controlled through [rebot-control](https://github.com/asEmbodiedAISyst/rebot-control). Read its safety page before you use the real arm.

## The arm frame

All positions in the scripts and in the calibration files are in the base frame of the arm. The origin is the centre of the base on its mounting surface. X points forward into the box, Y points to the left when you stand behind the arm, and Z points up. Lengths are in metres.

## Install

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
uv sync --group robot --python 3.12
```

The dependency group `robot` holds what the scripts import: rebot-control with its simulator, imuninn, OpenCV, PyAV, pyarrow and some smaller packages. The package `asfinger` itself does not need this group.

- rebot-control is not on PyPI. `pyproject.toml` takes it from GitHub at a fixed commit.
- The group is tested with Python 3.12. Pinocchio, which rebot-control uses, has no package for the newest Python versions at once.
- `motorbridge`, the driver of the motors, is installed on Linux only. On macOS you can use everything that has `--sim`.

Run a script from the root of the repository:

```bash
uv run python robot/arm_move.py --help
```

## The CAN bus

The motors answer on the SocketCAN interface `can0` at 1 Mbit/s. After a restart of the computer, or after you plug the adapter in again, the interface is down. Bring it up:

```bash
sudo ip link set can0 type can bitrate 1000000 restart-ms 100 && sudo ip link set can0 up
```

Only one program can be connected to the arm at a time. A second program stops with an error.

## The phones

Put the phones and the computer on the same local network. Then tell the scripts where the phones are:

1. Copy `robot/cameras.example.yaml` to `robot/cameras.local.yaml`. Git ignores the copy, so your addresses stay on your computer.
2. Find each phone with `uv run imuninn list` and write its address or its iMuninn name into the file.
3. Run `uv run python robot/snapshot.py --cam top`. The tool prints a warning with the device id of the phone that answered. Copy that id into the file. Do the same with `--cam wrist`.

| Key | Meaning |
| --- | --- |
| `address` | Address or iMuninn name of the phone. `ASFINGER_TOP_CAM` and `ASFINGER_WRIST_CAM` replace it for one run. The earlier names `IPUSH_TOP_CAM` and `IPUSH_WRIST_CAM` still work. |
| `device_id` | The id that the phone reports. A tool warns when another phone answers at the address. |
| `label` | Your name for the phone. It appears in messages only. |

A tool that needs a phone stops with a message when `robot/cameras.local.yaml` is absent.

### Camera profiles

The configuration of each phone is a profile file:

| Profile | Lens and format | Exposure and white balance |
| --- | --- | --- |
| `robot/top_camera.yaml` | Ultra wide, 1920 × 1440 at 60 fps | Manual, so that pictures from different times can be compared. |
| `robot/wrist_camera.yaml` | Ultra wide, 640 × 480 at 60 fps | Automatic, because the view changes when the arm moves. |

The ultra wide lens has the same field of view in every 4:3 format, about 103° × 86°. The wrist camera uses the small format because it needs less storage and decodes faster.

A phone goes back to its defaults when the iMuninn app restarts. The tools compare the phone with its profile and print a warning with the command that applies the profile again:

```bash
uv run imuninn profile apply robot/top_camera.yaml <address of the top phone>
```

The manual exposure and white balance of the top camera come from `robot/calibrate_color.py` and the colour card. Run it again when the light changes. See [Calibration](robot-calibration.md#the-colour-card).

### Look at the workspace

```bash
uv run python robot/snapshot.py -o top.jpg                 # top camera
uv run python robot/snapshot.py --cam wrist -o wrist.jpg   # wrist camera
uv run python robot/tags.py top.jpg                        # the markers in a picture: id, size, centre, corners
```

- `snapshot.py` starts the capture session of the phone when it is off, and stops it again after the shot. Add `--keep-running` when you take many shots.
- The picture is saved in the orientation of the sensor. The camera intrinsics and the marker detections use the same orientation.
- `snapshot.py` does not change the configuration of the phone.

The capture session is a state of the phone and stays on when a connection ends. Stop only a session that you started, because another program can be using the same phone.

## Limits

- **The top camera looks at an angle.** An object near the arm is much smaller in the picture than an object below the camera. Do not use pixel distances as a scale. Use the markers on the table.
- **No lens model.** The phones do not report distortion coefficients. Inside the whiteboard area, lengths measured with the top camera were right to about 1 %. With the wrist camera the error reached 8 % in the corners of the picture.
- **Small markers.** At 640 × 480 the wrist camera finds a 50 mm marker at 35 cm reliably. A 30 mm marker at that distance is not reliable.
- **The checks know little about the arm.** The limit checks of the scripts use the joint centres, the tool tip and the phone on the tool. They do not know the shape of the links, the cables or objects on the table.
