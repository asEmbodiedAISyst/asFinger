# Quick start

This page builds the default tool and explains each output file.

## Build a config

Run the command from the root of the repository:

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/iphone17pro_default
```

The command prints a report and writes this folder:

```text
out/iphone17pro_default/
├── print/
│   ├── ipush_print.stl    the pusher and the phone holder fused into one body
│   ├── tool_body.stl      the pusher alone
│   └── holder.stl         the phone holder alone
├── meshes/                one STL for each part, used by the MJCF file
├── ipush_tool.xml         the MuJoCo model
├── preview.html           a 3D preview for the browser
├── resolved.json          every frame and shape with its numbers computed
└── report.json            volume, mass and check results
```

The file names `ipush_print.stl` and `ipush_tool.xml` come from an earlier name of the project. They are kept so that existing tools continue to work.

## The output files

| File | Content |
| --- | --- |
| `print/<part>.stl` | One file for each part with `"role": "printed"`, in the frame of that part. |
| `print/<set>.stl` | One file for each print set: its parts fused into one body. In the default config, the mounting face of the pusher base is on z = 0. Put this face on the print bed. |
| `meshes/<part>.stl` | Every part, in the frame of the MJCF body. |
| `ipush_tool.xml` | Collision shapes, visual meshes, mass and inertia, one site for each frame, and the cameras. See [MuJoCo export](mjcf.md). |
| `preview.html` | Parts, frames, collision shapes and the view of the camera `C_main`. |
| `resolved.json` | Input for other programs: frames as position and quaternion, and the shape trees with numeric sizes. |
| `report.json` | For each part: volume, mass and triangle count. For each print set: the number of bodies. Also the total mass and the failed interference rules. |

The STL files are binary, in millimetres.

> **Limits of the preview.** `preview.html` loads three.js from a CDN, so it needs an internet connection. The page also needs a camera named `C_main` in the config. Without that camera, for example with `--option phone=0`, the page stays empty.

> **A local path in the output.** `resolved.json` stores the absolute path of the folder that holds `configs/` and `assets/` (the key `base_dir`). Remove this key before you share the file.

## Change a parameter

Use `--set` to change a parameter for one build. The config file does not change.

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/short --resolve --set rod_L=160 --set rod_tilt=25
```

The pose of the phone is a solved frame: a solver computes it from the rod and the camera. The config stores the last result. Add `--resolve` each time you change a parameter that the solver uses. Without `--resolve`, the build uses the stored pose and prints this warning:

```text
[warn] P_phone: saved result is stale (inputs changed); run with --resolve to update
```

`--resolve` without `--set` and without `--option` also writes the new result into the config file. See [Frames](frames.md#solved-frames).

## Switch an option

An option turns a group of frames and parts off. This command builds the rod without the phone and its holder:

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/rod_only --option phone=0
```

## List the frames

```bash
asfinger frames hardware/configs/iphone17pro_default.json
```

Each line gives the frame name, its position in the root frame, the direction of its Z axis, and the source of the pose (`module` or `solved`).

## Use the package from Python

```python
from asfinger import Model

m = Model.load('hardware/configs/iphone17pro_default.json')
for length in (140, 160, 180):
    m.copy().set(rod_L=length).build(f'out/rod_{length}', resolve=True)
```

Useful calls:

| Call | Result |
| --- | --- |
| `Model.load(path)` | A model from a config file. |
| `m.set(name=value)` | Change parameters. An unknown name raises `KeyError`. |
| `m.set_options(phone=False)` | Switch options. |
| `m.frames(resolve=False)` | `(world, local, info)`: the pose of each frame in the root frame and in its parent. |
| `m.root_to('T_tcp')` | The pose of one frame in the root frame. Use it as the TCP offset on the robot. |
| `m.check()` | The messages of the failed checks. An empty list means no failure. |
| `m.interference()` | The messages of the failed interference rules. |
| `m.build(out_dir, resolve=False)` | Write all outputs. Returns the resolved model and the report. |

A pose has the attributes `p` (position, a list of 3 numbers) and `R` (rotation matrix), and the method `quat()` (`[w, x, y, z]`).

## The other configs

| Config | Tool |
| --- | --- |
| `iphone17pro_default.json` | The pusher for the iPhone 17 Pro on the reBot Arm B601-RS, mounted on the gripper connector of the arm. |
| `rebot_rs_flange.json` | The same pusher without the mount adapter. The base is bolted to the joint-6 rotor of the reBot arm. |
| `square_rod.json` | The earlier pusher with a 10 × 10 mm square rod and a flat end (the Square pusher of the editor); otherwise like `iphone17pro_default.json`, without the back reinforcement of the holder. |
