# Arm tools and safety rules

The scripts in `robot/` move a real arm. This page gives the rules for their use, the behaviour of the arm when a program fails, and the purpose of each tool.

> **Status.** These tools were moved here from the working repository of the setup. They have not been run on the real arm from this repository yet. Run each tool with `--sim` first.

## Rules

- Use the real arm only with an operator beside it, at the power switch of the motors.
- Before a command switches torque on, moves the arm or switches torque off, say what will happen and what the worst case is. Wait for the operator to agree.
- Try a new motion in the simulator first (`--sim`).
- Do not loosen a safety limit of the control library.
- The printed pusher cannot take a large force. When the pusher must touch something, the operator decides when it touches. The detection in the program is a backup only.

The safety model of the control library is in the documentation of [rebot-control](https://github.com/asEmbodiedAISyst/rebot-control) (`docs/user/safety.md`). It applies here too.

## What the arm does when something fails

Torque goes off only on purpose.

| Event | Behaviour of the arm |
| --- | --- |
| A program ends normally | The arm folds to its zero pose in steps. Then torque goes off. |
| A program fails, gets Ctrl-C or is killed, the computer stops, the CAN cable comes off | The arm holds where it is. The motors stay enabled, also after the program is gone. |
| The library detects a stall | The arm holds where it is, enabled. |
| A motor driver gets too hot (above 125 °C) | Torque goes off and the arm drops. This is the only automatic torque-off. |
| The operator runs the release command | Torque goes off. |

An arm that was left holding has no program that watches it. There is no stall check and no temperature check, and the motors keep giving torque. The drivers get warm during a long hold. End the hold with one of these commands:

```bash
robot/arm state              # is the arm enabled and holding? This changes nothing.
robot/arm release --fold     # fold from the present pose to the zero pose, then torque off
robot/arm release            # torque off now: support the arm with your hand first
```

`robot/arm` is the command line of rebot-control with the tool model and the calibration of this arm filled in. Every other rebot-control command works through it in the same way. It uses `.venv/bin/rebot-control` when that exists, and `uv run --group robot rebot-control` otherwise.

When the next program connects and finds the motors enabled, it takes the hold over without a jump and continues from there.

## The tools

Each tool prints its usage with `--help`, except the two that the table marks. On the real arm, a tool that moves the arm prints its plan and moves nothing unless you add `--yes`.

| Tool | Function |
| --- | --- |
| `arm` | The rebot-control command line for this arm: `robot/arm state`, `robot/arm release`. |
| `arm_sign_check.py` | Sign check by hand. Torque stays off. The operator moves each joint and the tool says if the direction agrees with the model. It takes no options and connects to the arm at once. |
| `arm_bus_check.py` | Read only. Asks each motor for its angle again and again and counts the answers. Use it to find a bad cable or connector. |
| `arm_hold.py` | Holds the present pose with torque on, records the motor data, then switches torque off. No other motion. |
| `arm_move.py` | Slow joint moves through a list of waypoints. It checks each waypoint and the path against the box before anything moves. |
| `arm_step_check.py` | A small step of selected joints at the home pose. It reports overshoot, rise time and settling time. Use it after a change of `kp` or `kd`. |
| `arm_line_test.py` | Moves the tool tip along straight lines above the table, records the run as an episode, and reports the deviations. |
| `arm_listen_ab.py` | A blind listening test: does a setting change how loud the motors are during a hold? It takes the name of the variant and, optionally, `--sim`; it has no `--help` and connects to the arm at once. |
| `arm_touch_table.py`, `arm_calib_gravity.py`, `arm_calib_ripple.py` | Calibration tools. See [Calibration](robot-calibration.md). |
| `teleop_iphone.py`, `teleop_star.py` | Teleoperation. See [Teleoperation](teleoperation.md). |
| `record.py`, `episode.py`, `to_lerobot.py`, `check_lerobot.py` | Recording and export. See [Data collection](data-collection.md). |
| `snapshot.py`, `tags.py`, `make_tags.py`, `calibrate_color.py` | Cameras and markers. See [The robot setup](robot-setup.md) and [Calibration](robot-calibration.md#markers). |

### Slow joint moves

```bash
uv run python robot/arm_move.py --waypoints "0,=,=,=,0,0; 0,15,20,=,0,0; 0,s,s,=,0,0" --sim
```

A waypoint is six joint angles in degrees. `=` keeps the joint where the waypoint before left it. `s` is the angle that the joint had when the program started. The tool refuses a plan that leaves the box of `calibration/workspace.yaml`.

`--end` selects what happens after the last waypoint:

| Value | Result |
| --- | --- |
| `hold` (default) | The arm keeps holding the last waypoint. End the hold with `robot/arm release`. |
| `off` | Torque goes off at the last waypoint. Use this only in a pose in which the arm can rest. |
| `fold` | The arm folds to the zero pose. Then torque goes off. |

### Hold test

```bash
uv run python robot/arm_hold.py --sim
uv run python robot/arm_hold.py --seconds 60 --record hold.npz
```

Start it with torque off and the arm in the folded pose. The tool stops and switches torque off when a joint moves more than 3° or a driver gets hotter than 60 °C. Unlike `rebot-control hold`, it does not fold the arm at the end.

### Straight-line test

```bash
uv run python robot/arm_line_test.py            # print the plan
uv run python robot/arm_line_test.py --yes      # run it on the arm, about 2 minutes
uv run python robot/arm_line_test.py --sim
uv run python robot/arm_line_test.py --from-data data/episodes/<name>   # make the report again
```

The rod is vertical and the orientation of the tool is fixed. The default route is a pattern of lines 6 cm above the table at 3, 6 and 10 cm/s, and one line 2 cm above the table at 3 and 6 cm/s. The table below the route must be empty.

For each line the report gives the deviation of the tip from the ideal line (sideways and in height), the distance behind the command, the tilt of the rod and the error at rest. These numbers come from the joint angles that the motors report. They show the view of the arm, not the true position of the tip in the room.

The test stops, lifts the tool and folds the arm when the tool is lower than 8 mm above the table, or when the tip is more than 1.5 cm from the commanded position.

## The home pose and the tool

- The home pose of the tool has the rod vertical and the tip at (0.24, 0, 0.12) m. The joint angles are [0, 71.4, 68.9, −57.6, 0, 0]°.
- The tool model is `calibration/tool_ip17pro_print.yaml`. The origin of the tool is the end of the rod and its Z axis is along the rod. The tools in `robot/` and the simulator load this file by default.
- The control library has a tool named `pusher_ip17`. It describes an older design. When you call `rebot-control` or `Arm.from_config` directly, pass the tool file and `--calibration calibration/b601_rs.yaml` yourself.

## Things to know

- **`rebot-control hold` and `home` fold the arm when they end.** To hold without other motion, use `robot/arm_hold.py`.
- **Torque off is not "stay where you are".** The joints go limp. The tool is not balanced about joint 6, so the side with the phone drops and the tool rolls by about 80°. Read the angle of joint 6 again each time before torque goes on.
- **The table is not at z = 0.** In the calibration of this setup the table is at z = +20 mm in the arm frame (`calibration/table.yaml`). The tip is a sphere with a radius of 7.5 mm.
- **Lag is not contact.** In slow motion the tip is between about 2 mm ahead of and 5 mm behind its target. Do not take a lag of a few millimetres as a sign of contact.
- **A motor that stops answering.** The control library keeps the last feedback of a motor when no new one arrives, so a lost connection looks like a stall after about a second. To find a bad connector, switch torque off and run `robot/arm_bus_check.py` while you move the arm by hand.
- **The messages for the operator in `arm_touch_table.py` and `arm_sign_check.py` are in Chinese.**
- **`arm_listen_ab.py kp` and `soft` stop with an error.** With the calibration file of this repository, the library refuses the halved `kp` because of the torque-ripple model. The variants `wrist-kd` and `filter` run.
- **The simulator does not show collisions of the arm.** In the scene only the pusher collides, and the contact values are estimates. See [Simulation](simulation.md).
