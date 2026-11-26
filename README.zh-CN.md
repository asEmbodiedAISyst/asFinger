# asFinger

[English](https://github.com/asEmbodiedAISyst/asFinger/blob/main/README.md) | 中文

一根装在机械臂或人手上的推杆，用手机当腕部相机。

工具是参数化的：一份 JSON 配置里写着参数、坐标系和实体形状。Python 包 `asfinger` 把它生成为可打印的 STL 和 MuJoCo
模型；[asFinger 编辑器](https://asembodiedaisyst.github.io/asFinger/zh/editor/)在浏览器里运行同一套代码。

## 安装

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
python3 -m pip install .
```

需要 Python 3.10 或更高版本。导入名是 `asfinger`。

## 快速上手

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/iphone17pro_default
```

命令会写出用于打印的 STL、MuJoCo 模型 `ipush_tool.xml`、HTML 预览和一份报告。

```python
from asfinger import Model

m = Model.load('hardware/configs/iphone17pro_default.json')
print(m.root_to('T_tcp').p)  # TCP position in the robot flange frame, mm
```

不想安装的话，直接打开[编辑器](https://asembodiedaisyst.github.io/asFinger/zh/editor/)设计推杆。

想在 Autodesk Fusion 里把工具当作参数化设计来改，用 `hardware/cad/fusion/` 里的插件
（[说明](https://asembodiedaisyst.github.io/asFinger/zh/docs/user/fusion/)）。

## 文档

网站：<https://asembodiedaisyst.github.io/asFinger/zh/docs/>

| 读者 | 从这里开始 |
| --- | --- |
| 使用者 | [使用指南](https://asembodiedaisyst.github.io/asFinger/zh/docs/user/)：安装、快速上手、配置文件、坐标系、检查、编辑器 |
| 开发者 | [开发指南](https://asembodiedaisyst.github.io/asFinger/zh/docs/developer/)：架构、设计决策、构建与测试 |
| AI agent | [AGENTS.md](https://github.com/asEmbodiedAISyst/asFinger/blob/main/AGENTS.md)、[Agent 指南](https://asembodiedaisyst.github.io/asFinger/zh/docs/agents/)、[llms.txt](https://asembodiedaisyst.github.io/asFinger/llms.txt)、[llms-full.txt](https://asembodiedaisyst.github.io/asFinger/llms-full.txt) |

## 许可证

MIT，见 [LICENSE](https://github.com/asEmbodiedAISyst/asFinger/blob/main/LICENSE)。编辑器里显示的机械臂模型沿用各自的许可证，见
[NOTICE](https://github.com/asEmbodiedAISyst/asFinger/blob/main/NOTICE)。
