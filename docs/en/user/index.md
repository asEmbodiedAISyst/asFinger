# User guide

This guide shows how to build a tool from a config, how to write a config, and how to use the web editor. The pages from "The robot setup" on are about the tool on a real arm: control, calibration, teleoperation and data.

| Page | Content |
| --- | --- |
| [Installation](installation.md) | Install the Python package. |
| [Quick start](quickstart.md) | Build a config into STL and MJCF. Read the output folder. |
| [The config file](config-file.md) | Parameters, parts, shapes, options, print sets and cameras, with a complete example. |
| [Frames](frames.md) | The frame tree, the frame names of the default tool, and solved frames. |
| [Checks and interference rules](checks.md) | What the generator checks, and what it does not check. |
| [MuJoCo export](mjcf.md) | What the MJCF file contains and how to attach it to a robot. |
| [The web editor](editor.md) | Configure, inspect and export in the browser. |
| [The Fusion add-in](fusion.md) | Build a config as a parametric design in Autodesk Fusion and update it in place. |
| [The robot setup](robot-setup.md) | The arm, the two phones and the box; install the robot-side software. |
| [Arm tools and safety rules](robot-arm-tools.md) | Rules for the real arm, what happens when a program fails, and each tool. |
| [Calibration](robot-calibration.md) | The calibration files in use, the tools that write them, the markers, the as-built frames. |
| [Teleoperation](teleoperation.md) | Move the arm with a hand-held iPhone or a leader arm. |
| [Data collection](data-collection.md) | Episodes, recording, and the export to a LeRobot dataset. |
| [Simulation](simulation.md) | The MuJoCo scene of the setup, and `--sim`. |
| [Troubleshooting](troubleshooting.md) | Messages and their causes. |

All lengths are in millimetres and all angles are in degrees, unless a page says otherwise. The MJCF file is the one exception: MuJoCo uses metres.
