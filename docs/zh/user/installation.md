# 安装

从仓库的克隆安装。克隆下来的仓库里同时有 `hardware/` 目录下的配置和网格。

## 环境要求

- Python 3.11 或更高版本。
- 安装时会装上 `numpy` 和 `manifold3d`，后者负责实体建模。
- MuJoCo 可选，只有要加载生成的模型时才需要。

网页编辑器不用安装，见[网页编辑器](editor.md)。

## 用 uv 安装

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
uv sync
uv run asfinger --help
```

`uv sync` 会建好 `.venv`，装上这个包和开发工具（pytest、ruff、MuJoCo）。

## 用 pip 安装

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
python3 -m pip install .
asfinger --help
```

要在 MuJoCo 里加载生成的模型，再运行 `python3 -m pip install mujoco`。

## 名称

项目叫 asFinger，Python 里导入时用小写：

```python
import asfinger
```

命令是 `asfinger`，和 `python -m asfinger` 等价。

## 检查安装结果

```bash
asfinger frames hardware/configs/iphone17pro_default.json
```

命令会把默认工具的每个坐标系打印一行，第一行是：

```text
F_robot   pos=[0.0, 0.0, 0.0]  z=[0.0, 0.0, 1.0]  module
```
