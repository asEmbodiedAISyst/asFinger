# asFinger documentation

asFinger is a push rod with a phone as the wrist camera, for a robot arm or a human hand. One JSON file describes the tool, and the `asfinger` Python package turns that file into printable STL files and a MuJoCo model.

The tool is parametric. The JSON file holds the parameters, a tree of coordinate frames, and solid shapes that are bound to those frames. Change a parameter, and every output follows.

The project has three parts:

- **The generator.** The Python package `asfinger` reads a config and writes STL files, a MuJoCo model (MJCF), an HTML preview and a report.
- **The web editor.** The [asFinger editor](https://asembodiedaisyst.github.io/asFinger/editor/) runs the same Python in the browser. You pick the robot arm, the mount adapter and the phone, change the parameters, and export the config and the STL.
- **The hardware inputs.** The folder `hardware/` holds the configs of the real tool and the meshes that they import.

## Where to start

| You want to | Read |
| --- | --- |
| Print a pusher for your arm | [Use the web editor](user/editor.md) |
| Build STL and MJCF on your computer | [Installation](user/installation.md), then [Quick start](user/quickstart.md) |
| Write or change a config | [The config file](user/config-file.md) and [Frames](user/frames.md) |
| Edit the tool as a CAD design | [The Fusion add-in](user/fusion.md) |
| Use the tool on a real arm | [The robot setup](user/robot-setup.md), then [Arm tools and safety rules](user/robot-arm-tools.md) |
| Record data with the arm | [Teleoperation](user/teleoperation.md) and [Data collection](user/data-collection.md) |
| Understand how the project works | [Developer guide](developer/index.md) |
| Use the project through an AI agent | [Agent guides](agents/index.md) |

## Status

The version is 0.1.0. The generator, the editor, the Fusion add-in, the robot-side tools with a first simulation scene, and these pages are public. The learning code is not in the repository. See the [roadmap](developer/roadmap.md).

The pusher for the iPhone 17 Pro on the Seeed reBot Arm B601-RS is printed and in use. Other arms in the editor use flange data from public datasheets. Values that are not confirmed are marked "to verify" in the editor.
