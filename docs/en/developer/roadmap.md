# State and roadmap

This page says what the repository contains today, what is known to be weak, and what is planned.

## State

The version is 0.1.0.

| Part | State |
| --- | --- |
| Generator (`src/asfinger`) | In use. It builds the printed pusher, the MuJoCo model and the preview. |
| Configs (`hardware/configs`) | Two configs: the pusher on the reBot gripper connector (default), and the same pusher bolted to the reBot flange. |
| Web editor | In use for the reBot Arm RS. Franka FR3 and UR5e use flange data from datasheets and are not tested on a real arm. |
| Fusion add-in (`hardware/cad/fusion`) | In the repository. Tried in Fusion by hand: build in a new document and update in place. |
| Robot-side tools (`robot/`, `calibration/`) | In the repository: arm tools, calibration, teleoperation, recording and export. They were moved from the working repository of the setup and are not run on the real arm from this repository yet. |
| Simulation (`sim/`) | Two MuJoCo scenes of the setup. The tools of `robot/` run in the first one with `--sim`. The twin scene has the arm meshes of the manufacturer (downloaded, not in the repository), the closed box, and lights and camera tone tuned to real pictures. |
| Documentation | English and Chinese, for users, developers and agents. |
| Tests | The default configs, the options, the checks and the interference rules, `asfinger send`, the parts of the Fusion add-in that run without Fusion, and the robot-side tools in the simulator. The STL export of the browser, the features that the add-in makes in Fusion, and everything that needs the real arm or a phone are not tested automatically. |

## Known weak points

- The command line prints check and interference messages in the default language of the config. It has no language option.
- `preview.html` needs a camera named `C_main` and an internet connection.
- `resolved.json` contains an absolute local path (`base_dir`).
- The mesh step exists twice, in `mesh.py` and in `site/src/engine/csg.ts`.
- The package has no type hints.
- The command `send` gets no result from the Fusion add-in, and the add-in accepts a request from any program on the computer. See [The Fusion add-in](../user/fusion.md#limits).
- A print set name, the MJCF body name and the output file names still use the earlier project name.
- The pusher base supports four screw holes only.
- The minimum focus distance of the phone cameras is unknown, so the focus check is off.
- The robot-side scripts are not a package. They run from the root of the repository and import each other by file name.
- The messages for the operator in two robot-side tools are in Chinese.
- Both simulation scenes have estimated contact values and no collision of the arm links.
- Rendering of the scenes is not tested in CI.

## Roadmap

These parts exist and will be added to this repository after review:

- the CAD exports and the records of the printed versions;
- the tools that register the twin scene from recorded video and replay episodes in it;
- pictures of the real setup;
- the learning code.

Planned for the generator and the editor:

- a base with six screw holes, for larger ISO flanges;
- more pushers, tips and cameras in the editor (the items marked "Planned").

The order is not fixed, and this page gives no dates.
