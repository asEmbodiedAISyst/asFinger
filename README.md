# asFinger

English | [中文](https://github.com/asEmbodiedAISyst/asFinger/blob/main/README.zh-CN.md)

A push rod with a phone as the wrist camera, for a robot arm or a human hand.

The tool is parametric. One JSON config holds the parameters, the coordinate frames and the solid shapes. The
`asfinger` Python package turns it into printable STL files and a MuJoCo model, and the
[asFinger editor](https://asembodiedaisyst.github.io/asFinger/editor/) runs the same code in the browser.

## Install

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
python3 -m pip install .
```

The package needs Python 3.11 or later. The import name is `asfinger`.

## Quick start

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/iphone17pro_default
```

The command writes the STL files to print, the MuJoCo model `ipush_tool.xml`, an HTML preview and a report.

```python
from asfinger import Model

m = Model.load('hardware/configs/iphone17pro_default.json')
print(m.root_to('T_tcp').p)  # TCP position in the robot flange frame, mm
```

To design a pusher without an installation, open the [editor](https://asembodiedaisyst.github.io/asFinger/editor/).

To edit the tool as a parametric design in Autodesk Fusion, use the add-in in `hardware/cad/fusion/`
([guide](https://asembodiedaisyst.github.io/asFinger/docs/user/fusion/)).

## On a real arm

`robot/` holds the scripts that use the tool on a Seeed reBot Arm B601-RS: arm tools, calibration, teleoperation
and data collection, with a MuJoCo scene in `sim/`. They need the dependency group `robot`:

```bash
uv sync --group robot --python 3.12
uv run python robot/arm_move.py --waypoints "0,15,20,=,0,0" --sim
```

Read [the robot setup](https://asembodiedaisyst.github.io/asFinger/docs/user/robot-setup/) and the
[safety rules](https://asembodiedaisyst.github.io/asFinger/docs/user/robot-arm-tools/) before you use the real arm.

## Documentation

Website: <https://asembodiedaisyst.github.io/asFinger/docs/>

| Reader | Start here |
| --- | --- |
| Users | [User guide](https://asembodiedaisyst.github.io/asFinger/docs/user/): installation, quick start, the config file, frames, checks, the editor |
| Developers | [Developer guide](https://asembodiedaisyst.github.io/asFinger/docs/developer/): architecture, design decisions, how to build and test |
| AI agents | [AGENTS.md](https://github.com/asEmbodiedAISyst/asFinger/blob/main/AGENTS.md), [agent guides](https://asembodiedaisyst.github.io/asFinger/docs/agents/), [llms.txt](https://asembodiedaisyst.github.io/asFinger/llms.txt), [llms-full.txt](https://asembodiedaisyst.github.io/asFinger/llms-full.txt) |

## License

MIT, see [LICENSE](https://github.com/asEmbodiedAISyst/asFinger/blob/main/LICENSE). The robot arm models shown in
the editor keep their own licences, see [NOTICE](https://github.com/asEmbodiedAISyst/asFinger/blob/main/NOTICE).
