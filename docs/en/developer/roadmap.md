# State and roadmap

This page says what the repository contains today, what is known to be weak, and what is planned.

## State

The version is 0.1.0.

| Part | State |
| --- | --- |
| Generator (`src/asfinger`) | In use. It builds the printed pusher, the MuJoCo model and the preview. |
| Configs (`hardware/configs`) | Two configs: the pusher on the reBot gripper connector (default), and the same pusher bolted to the reBot flange. |
| Web editor | In use for the reBot Arm RS. Franka FR3 and UR5e use flange data from datasheets and are not tested on a real arm. |
| Documentation | English and Chinese, for users, developers and agents. |
| Tests | The default configs, the options, the checks and the interference rules. The STL export of the browser is not tested automatically. |

## Known weak points

- The command line prints check and interference messages in the default language of the config. It has no language option.
- `preview.html` needs a camera named `C_main` and an internet connection.
- `resolved.json` contains an absolute local path (`base_dir`).
- The mesh step exists twice, in `mesh.py` and in `site/src/engine/csg.ts`.
- The package has no type hints.
- The command `send` talks to a CAD add-in that is not in this repository.
- A print set name, the MJCF body name and the output file names still use the earlier project name.
- The pusher base supports four screw holes only.
- The minimum focus distance of the phone cameras is unknown, so the focus check is off.

## Roadmap

These parts exist and will be added to this repository after review:

- the CAD exports and the records of the printed versions;
- the simulation of the tool on a robot arm;
- the robot-side code: calibration, teleoperation and data collection;
- the learning code.

Planned for the generator and the editor:

- a base with six screw holes, for larger ISO flanges;
- more pushers, tips and cameras in the editor (the items marked "Planned").

The order is not fixed, and this page gives no dates.
