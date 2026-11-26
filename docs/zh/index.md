# asFinger 文档

asFinger 是一根装在机械臂或人手上的推杆，用手机当腕部相机。整个工具由一份 JSON 文件描述，Python 包 `asfinger` 读这份文件，生成可以直接打印的 STL 和 MuJoCo 模型。

工具是参数化的。JSON 文件里写着参数、坐标系树，以及绑在坐标系上的实体形状。改一个参数，所有输出跟着变。

项目分三部分：

- **生成器。** Python 包 `asfinger` 读配置，输出 STL、MuJoCo 模型（MJCF）、HTML 预览和一份报告。
- **网页编辑器。** [asFinger 编辑器](https://asembodiedaisyst.github.io/asFinger/zh/editor/)在浏览器里运行同一套 Python。选好机械臂、法兰转接件和手机，调参数，然后导出配置和 STL。
- **硬件输入。** `hardware/` 目录存放实物工具的配置，以及配置引用的网格文件。

## 从哪里开始

| 想做的事 | 看这里 |
| --- | --- |
| 给自己的机械臂打印一根推杆 | [网页编辑器](user/editor.md) |
| 在自己电脑上生成 STL 和 MJCF | [安装](user/installation.md)，然后看[快速上手](user/quickstart.md) |
| 写配置或改配置 | [配置文件](user/config-file.md)和[坐标系](user/frames.md) |
| 了解项目怎么工作 | [开发指南](developer/index.md) |
| 让 AI agent 来用这个项目 | [Agent 指南](agents/index.md) |

## 现状

当前版本 0.1.0。生成器、编辑器和这套文档已经公开。仿真、机器人侧代码和学习代码还没有放进仓库，见[路线图](developer/roadmap.md)。

iPhone 17 Pro 配 Seeed reBot Arm B601-RS 的推杆已经打印出来并在使用。编辑器里其他机械臂的法兰数据来自公开的数据手册，没有确认过的数值在编辑器里标着“待核实”。
