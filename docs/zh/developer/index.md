# 开发指南

这部分写给想弄懂或者想修改这个项目的人。

| 页面 | 内容 |
| --- | --- |
| [架构](architecture.md) | 一份配置怎样变成坐标系、实体和文件；Python 里和浏览器里各是怎么做的。 |
| [设计决策](decisions.md) | 主要的决策和理由。 |
| [构建、测试与贡献](contributing.md) | 搭环境、跑检查、写文档、提交修改。 |
| [现状与路线图](roadmap.md) | 现在有什么，已知的薄弱之处，接下来做什么。 |

仓库结构：

| 路径 | 内容 |
| --- | --- |
| `src/asfinger/` | 生成器，一个 Python 包。 |
| `tests/` | 生成器和文档的测试。 |
| `hardware/configs/` | 实物工具的配置。 |
| `hardware/assets/` | 配置引用的网格。 |
| `hardware/cad/fusion/` | Autodesk Fusion 的插件和脚本。 |
| `robot/` | 真机用的脚本：机械臂工具、标定、遥操作、录制。 |
| `calibration/` | 机械臂和工具在用的标定文件。 |
| `sim/` | 这套设备的 MuJoCo 场景。 |
| `data/` | 录下来的 episode。只有它的 README 在 git 里。 |
| `site/` | 网站：首页、编辑器和文档站。 |
| `docs/en/`、`docs/zh/` | 文档源文件，英文和中文各一套。 |
