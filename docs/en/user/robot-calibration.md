# Calibration

The folder `calibration/` holds the results that the tools in `robot/` read: the gains and model parameters of one arm, the tool model, the table height and the size of the workspace. They are the values in use on the setup of this project. Use them as a reference: for another arm, another tool or another box you must make your own.

The raw measurements behind these files are not in the repository. The tools write them to `calibration/data/`, which git ignores.

## The files

| File | Content | Written by |
| --- | --- | --- |
| `calibration/b601_rs.yaml` | The arm: position gains, link masses and centres of mass, the torque-ripple model, dry friction and the share of it that is fed forward. | `arm_calib_gravity.py`, `arm_calib_ripple.py`; the gains by hand |
| `calibration/tool_ip17pro_print.yaml` | The tool: where the tool frame and the phone sit on the flange, the tip radius, the payload, the home pose, the Cartesian limits. | by hand, from the as-built frames below |
| `calibration/table.yaml` | The height of the table in the arm frame, as the arm measures it. | `arm_touch_table.py` |
| `calibration/workspace.yaml` | The box that the arm may use, the margin to it, and the clearance above the table. | by hand, from a ruler |
| `calibration/star_leader.yaml` | The leader arm for teleoperation: port, servo ids, signs, offsets, ranges. | by hand |

Pass the arm file to rebot-control with `--calibration calibration/b601_rs.yaml` and the tool file with `--tool calibration/tool_ip17pro_print.yaml`. The tools in `robot/` and `robot/arm` do this by default.

### Values in use

| Item | Value |
| --- | --- |
| `kp`, joints 1 to 6 | 80, 120, 120, 40, 40, 40 |
| `kd`, joints 1 to 6 | 4, 4, 4, 4, 3.2, 3.2 |
| Friction feedforward | 0.7 of the measured dry friction, joints 1 to 3 |
| Torque ripple | 126 periods for each turn of joints 1 to 3 (the RS-06 motors), fed forward from the measured joint angle |
| Table height | z = +19.7 mm in the arm frame |
| Workspace box | x −0.45 to 0.65 m, y ±0.40 m, z 0 to 0.70 m; margin 0.10 m; clearance above the table 0.03 m |
| Home pose | [0, 71.4, 68.9, −57.6, 0, 0]°: rod vertical, tip at (0.24, 0, 0.12) m |
| Cartesian limits of the tool | x 0.19 to 0.50 m, y ±0.20 m, z 0.025 to 0.20 m |

The gains differ from the defaults of the library. With the default `kd` of 8 the shoulder and elbow motors hum on this arm, so their `kd` is 4. The base joint has `kp` 80 because of its torque ripple.

### Limits of these values

- **The gain of joint 1 is not step-checked on the real arm.** Run `robot/arm_step_check.py --joints 1` before you depend on it.
- **The gravity model is right to about the static friction of the joints**, 0.1 to 0.4 N·m, and only inside the range of poses of the calibration.
- **The ripple model belongs to the zero of each joint.** Calibrate again after you set the zero of a motor.
- **The compensation is not complete.** At slow speed the height of the tip still moves by a few millimetres along a straight line, and you can see it.
- **The table height is not a geometric height.** It is the height at which the model of the arm puts the tip when the tip touches. It includes the errors of the model.
- **The offset of the tool along the flange axis, 8.98 mm, is inferred, not measured.**
- **The payload in the tool file is copied from an older tool model**, because the gravity calibration was fitted with it. The real weights are not measured.
- **`calibration/star_leader.yaml` is not checked against a real leader arm.** See [Teleoperation](teleoperation.md#with-a-leader-arm).

## The calibration tools

All tools print their plan and move nothing on the real arm unless you add `--yes`. All of them have `--sim`. The rules of [Arm tools and safety rules](robot-arm-tools.md) apply.

| Tool | What it does | Result |
| --- | --- | --- |
| `arm_calib_gravity.py` | Visits static poses inside the box and averages the motor torques. It fits the mass and the centre of mass of each link, with the tool mounted. | `link_params` in `b601_rs.yaml` |
| `arm_calib_ripple.py` | Moves one joint at a time slowly back and forth and fits the torque that changes with the joint angle. It also gives the dry friction. | `ripple` and `friction` in `b601_rs.yaml` |
| `arm_touch_table.py` | Lowers the tool tip onto free spots of the table. The operator says when the tip touches. | `table.yaml` |
| `arm_step_check.py` | A small step of selected joints at the home pose. | a report; nothing is written |
| `calibrate_color.py` | Finds the manual exposure and white balance of a camera with the colour card. | values for the camera profile |

Each tool saves its measurements in `calibration/data/`. `--from-data` makes the fit again from a saved file without the arm, for example after the tool model changed. `--no-save` leaves the calibration file as it is.

### Touch the table

```bash
uv run python robot/arm_touch_table.py            # print the plan
uv run python robot/arm_touch_table.py --yes      # run it in a terminal beside the arm
uv run python robot/arm_touch_table.py --sim --auto
```

The operator runs the tool in a terminal beside the arm. For each point:

1. The tip moves to 5 cm above the point and stops.
2. Press Enter. The tip goes down at 3 mm/s. Press Enter again to stop it a little above the table.
3. Each further Enter lowers the tip by 0.5 mm. A number lowers it by that many millimetres, and a negative number lifts it. `c` continues the slow descent.
4. When you see the tip touch the table, type `t`. The joint angles of that moment are the measurement. `s` skips the point and `q` ends the run.

The program has its own contact detection as a backup. It stops the descent when the tip is 3 mm higher than its target, or when a motor torque changes by more than 1.5 N·m. Then it lifts the target to 1 mm above the tip and asks the operator.

- The points must be free spots of the table: no marker, no paper, no object.
- On the real arm the backup stops the descent in free air now and then, because the lag of the tip changes by several millimetres in slow motion. The pusher is not loaded when that happens. Answer that the tip did not touch, and continue.
- `--auto` lets the program decide. Use it in the simulator only.
- The prompts of this tool are in Chinese.

## Markers

The markers are AprilTag 36h11. The size is the edge of the black square. The id fixes the size, in the code too (`robot/tags.py`):

| Id | Edge |
| --- | --- |
| 0 to 9 | 50 mm |
| 10 to 19 | 40 mm |
| 20 to 29 | 70 mm |
| 30 to 89 | 30 mm |
| 90 to 99 | 30 mm, on the colour card |

In this setup, markers 1 and 2 are on two opposite corners of the whiteboard, marker 10 is on the base of the arm, and the colour card with markers 90 and 91 lies on the whiteboard. The whiteboard and the card can be moved.

Detection uses OpenCV (`cv2.aruco`, `DICT_APRILTAG_36h11`). The AprilTag library reads the same markers, but its corner order is different. Do not mix the two.

```bash
uv run python robot/make_tags.py                                  # the default set, as apriltag-36h11-a4.pdf
uv run python robot/make_tags.py --spec "50:0-5,40:10-15" -o tags.pdf
```

The PDF is A4 and drawn in millimetres. Print it at 100 %, not "fit to page". Each page has a 100 mm scale line: measure it after printing. Use matt paper, and keep the white border inside the grey cut line.

- **A small marker gives a position, not a frame.** A marker that is only 30 pixels wide in the picture has a stable centre, but its orientation can flip. Do not build a frame on the 6-DOF pose of one small marker.
- The marker on the base is hidden by the phone on the tool when the arm leans forward.

### The colour card

The card is 190 × 50.5 mm with a marker at each end. The top row is white (bare paper), 75 %, 50 % and 25 % grey, and black. The bottom row is red, yellow, green, blue and magenta. `make_tags.py` draws it and `calibrate_color.py` finds its patches in a picture.

```bash
uv run python robot/calibrate_color.py --cam top --check   # read the card, change nothing
uv run python robot/calibrate_color.py --cam top           # search, and leave the phone on the result
```

The second command prints the values to copy into `robot/top_camera.yaml`. A desktop printer does not give known colours, so the card is a neutral reference for white balance and a check that pictures stay the same. It is not an absolute colour standard.

## The frames of the pusher as built

This table gives the frames of the pusher that is on the arm (the version printed on 2026-11-08, phone case 3.25 mm), from the generator of this project. It is the source of the tool file. Positions are in millimetres and quaternions are `[w, x, y, z]`. "World" is the root frame `F_robot`, the mounting face of the pusher. The frame names are explained in [Frames](frames.md).

| Frame | Parent | World position | World quaternion | Local position | Local quaternion |
| --- | --- | --- | --- | --- | --- |
| `F_robot` |  | [0.000, 0.000, 0.000] | [1.000000, 0.000000, 0.000000, 0.000000] | [0.000, 0.000, 0.000] | [1.000000, 0.000000, 0.000000, 0.000000] |
| `F_mount` | `F_robot` | [0.000, 0.000, 0.000] | [1.000000, 0.000000, 0.000000, 0.000000] | [0.000, 0.000, 0.000] | [1.000000, 0.000000, 0.000000, 0.000000] |
| `F_tool` | `F_mount` | [0.000, 0.000, 10.000] | [1.000000, 0.000000, 0.000000, 0.000000] | [0.000, 0.000, 10.000] | [1.000000, 0.000000, 0.000000, 0.000000] |
| `R_rod` | `F_tool` | [7.890, 0.000, 10.000] | [0.965926, 0.000000, 0.258819, 0.000000] | [7.890, 0.000, 0.000] | [0.965926, 0.000000, 0.258819, 0.000000] |
| `T_tip` | `R_rod` | [96.340, 0.000, 163.200] | [0.965926, 0.000000, 0.258819, 0.000000] | [0.000, 0.000, 176.900] | [1.000000, 0.000000, 0.000000, 0.000000] |
| `T_tcp` | `T_tip` | [100.090, 0.000, 169.695] | [0.965926, 0.000000, 0.258819, 0.000000] | [0.000, 0.000, 7.500] | [1.000000, 0.000000, 0.000000, 0.000000] |
| `P_phone` | `F_tool` | [-41.252, -41.390, 70.168] | [0.462832, -0.000000, -0.886446, -0.000000] | [-41.252, -41.390, 60.168] | [0.462832, -0.000000, -0.886446, -0.000000] |
| `B_back` | `P_phone` | [-34.073, -41.390, 75.169] | [0.462832, -0.000000, -0.886446, -0.000000] | [0.000, 0.000, -8.750] | [1.000000, 0.000000, 0.000000, 0.000000] |
| `C_main` | `P_phone` | [-44.850, 0.000, 93.931] | [0.327272, 0.626812, -0.626812, -0.327272] | [21.555, 41.390, -10.630] | [0.707107, 0.000000, -0.000000, -0.707107] |
| `C_cv` | `C_main` | [-44.850, 0.000, 93.931] | [0.626812, -0.327272, 0.327272, -0.626812] | [0.000, 0.000, 0.000] | [0.000000, 1.000000, 0.000000, 0.000000] |
| `C_ultrawide` | `P_phone` | [-44.850, 19.240, 93.931] | [0.327272, 0.626812, -0.626812, -0.327272] | [21.555, 60.630, -10.630] | [0.707107, 0.000000, -0.000000, -0.707107] |
| `C_ultrawide_cv` | `C_ultrawide` | [-44.850, 19.240, 93.931] | [0.626812, -0.327272, 0.327272, -0.626812] | [0.000, 0.000, 0.000] | [0.000000, 1.000000, 0.000000, 0.000000] |
| `C_tele` | `P_phone` | [-34.568, 9.620, 79.169] | [0.327272, 0.626812, -0.626812, -0.327272] | [3.565, 51.010, -10.630] | [0.707107, 0.000000, -0.000000, -0.707107] |
| `C_tele_cv` | `C_tele` | [-34.568, 9.620, 79.169] | [0.626812, -0.327272, 0.327272, -0.626812] | [0.000, 0.000, 0.000] | [0.000000, 1.000000, 0.000000, 0.000000] |
| `S_lidar` | `P_phone` | [-19.895, -0.550, 58.105] | [0.327272, 0.626812, -0.626812, -0.327272] | [-22.105, 40.840, -10.630] | [0.707107, 0.000000, -0.000000, -0.707107] |
| `L_flash` | `P_phone` | [-19.895, 19.790, 58.105] | [0.327272, 0.626812, -0.626812, -0.327272] | [-22.105, 61.180, -10.630] | [0.707107, 0.000000, -0.000000, -0.707107] |
| `C_front` | `P_phone` | [-45.439, 25.620, 76.178] | [0.626812, 0.327272, 0.327272, 0.626812] | [7.325, 67.010, 0.000] | [0.000000, 0.707107, 0.707107, 0.000000] |
| `C_front_cv` | `C_front` | [-45.439, 25.620, 76.178] | [0.327272, -0.626812, -0.626812, 0.327272] | [0.000, 0.000, 0.000] | [0.000000, 1.000000, 0.000000, 0.000000] |
| `S_mount` | `P_phone` | [-31.406, -41.390, 77.027] | [0.462832, -0.000000, -0.886446, -0.000000] | [0.000, 0.000, -12.000] | [1.000000, 0.000000, 0.000000, 0.000000] |
| `J_foot` | `F_tool` | [0.000, -41.390, 40.688] | [1.000000, 0.000000, 0.000000, 0.000000] | [0.000, -41.390, 30.688] | [1.000000, 0.000000, 0.000000, 0.000000] |
| `J_bend` | `F_tool` | [0.000, -41.390, 40.688] | [0.698943, -0.107141, -0.107141, 0.698943] | [0.000, -41.390, 30.688] | [0.698943, -0.107141, -0.107141, 0.698943] |

The cameras, with a 4:3 picture: `C_main` has a vertical field of view of 56.8°, `C_ultrawide` 88.4° and `C_tele` 14.8°. The wrist video comes from the ultra wide lens.

How `F_robot` sits on the flange frame `link6` of the arm is not in this table. The tool file uses a rotation of 180° about the flange axis and an offset of 8.98 mm along it.
