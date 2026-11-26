# Installation

Install the package from a clone of the repository. The clone also gives you the configs and meshes in `hardware/`.

## Requirements

- Python 3.11 or later.
- The package installs `numpy` and `manifold3d`. `manifold3d` does the solid modelling.
- MuJoCo is optional. You need it only to load the generated model.

The web editor needs no installation. See [The web editor](editor.md).

## Install with uv

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
uv sync
uv run asfinger --help
```

`uv sync` creates `.venv` and installs the package together with the development tools (pytest, ruff, MuJoCo).

## Install with pip

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
python3 -m pip install .
asfinger --help
```

To load the generated model in MuJoCo, also run `python3 -m pip install mujoco`.

## Names

The project is named asFinger. The Python import name is lowercase:

```python
import asfinger
```

The command is `asfinger`. `python -m asfinger` does the same.

## Check the installation

```bash
asfinger frames hardware/configs/iphone17pro_default.json
```

The command prints one line for each frame of the default tool. The first line is:

```text
F_robot   pos=[0.0, 0.0, 0.0]  z=[0.0, 0.0, 1.0]  module
```
