# Use asFinger for a user

This page is for an agent that builds or edits a tool config for a person.

## Install

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
python3 -m pip install .
```

- The package needs Python 3.11 or later.
- The import name is `asfinger` (lowercase). The command is `asfinger`.
- The configs are in `hardware/configs/`. The meshes they import are in `hardware/assets/`.

## Entry points

| Entry point | Function |
| --- | --- |
| `asfinger build CONFIG -o OUT` | Write STL, MJCF, preview, `resolved.json` and `report.json` to `OUT`. |
| `asfinger frames CONFIG` | Print the pose of each frame. |
| `--set NAME=VALUE` | Change a parameter for this run. Repeat the flag for more parameters. |
| `--option NAME=0` or `NAME=1` | Switch an option for this run. |
| `--resolve` | Run the solvers again. Without `--set` and `--option`, this also rewrites the config file. |
| `from asfinger import Model` | The Python interface. |

## Common calls

Build the default tool:

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/default
```

Build a variant and keep the config file unchanged:

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/variant --resolve --set rod_L=160 --set rod_tilt=25
```

Get the TCP pose and the test results in Python:

```python
from asfinger import Model

m = Model.load('hardware/configs/iphone17pro_default.json').set(rod_L=160)
R = m.resolve(resolve=True)  # solve again after a parameter change
tcp = m.root_to('T_tcp', R)  # pose in the root frame F_robot
print(tcp.p, tcp.quat())  # mm, [w, x, y, z]
print(m.check(R, lang='en'))  # [] = no failed check
print(m.interference(R, lang='en'))  # [] = no overlap
m.build('out/rod_160', resolve=True)
```

Save a changed config as a new file:

```python
m.cfg['name'] = 'my_variant'
m.save('hardware/configs/my_variant.json')
```

## Inputs and outputs

- Input: one JSON config. The format is in [The config file](../user/config-file.md) and [Frames](../user/frames.md).
- Units: millimetres, degrees, g/cm³. The MJCF file is in metres. Quaternions are `[w, x, y, z]`.
- `Model.frames()` returns `(world, local, info)`. `world[name]` is a pose with `.p` (position), `.R` (3×3 matrix) and `.quat()`.
- `Model.build(out_dir)` returns `(resolved, report)` and writes the files listed in [Quick start](../user/quickstart.md#the-output-files).
- `Model.check()` and `Model.interference()` return lists of strings. An empty list means that no test failed.
- Errors: `KeyError` for an unknown parameter or option, `asfinger.expr.ExprError` for a bad expression, `ValueError` for a bad frame tree or a mesh that is not a closed solid, `FileNotFoundError` for a missing mesh.

## Rules

- After you change a parameter, pass `--resolve` (command line) or `resolve=True` (Python). Without it, the phone pose is stale and the checks are not valid.
- Before you tell the user that a variant is ready to print, confirm that `check()` and `interference()` return empty lists and that each print set in `report.json` has `"bodies": 1`.
- If a test fails, report the message and the rule name to the user. Do not raise `tol_mm3` or remove a rule to make it pass.
- Do not run `asfinger build ... --resolve` without `--set` on a config in `hardware/configs/` unless the user asks you to update that file. That command rewrites the file.
- Write a variant to a new file. Do not overwrite `iphone17pro_default.json` or `rebot_rs_flange.json`.
- Keep a config in a folder that has `assets/` as its neighbour. Mesh paths in a config are relative to the parent of the config folder.
- Before you share `resolved.json`, remove the key `base_dir`. It contains a local path.
- Use `asfinger send` only when the user asks for it and runs the [Fusion add-in](../user/fusion.md). The command changes the design that is open in Fusion, and `--save` rewrites the config file. It does not return the result: ask the user what the palette shows.
- Tell the user about the limits that apply to their request. The pages [Checks and interference rules](../user/checks.md#what-the-tests-do-not-find) and [Frames](../user/frames.md#known-limits-of-the-phone-frames) list them. `back_to_mount` must match the phone case of the user.
- If the user has no Python environment, send them to the [web editor](https://asembodiedaisyst.github.io/asFinger/editor/).
