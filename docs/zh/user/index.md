# 使用指南

这部分讲怎样从配置生成工具、怎样写配置、怎样用网页编辑器。从“真机环境”开始的几页讲工具装到真机上以后的事：控制、标定、遥操作和数据。

| 页面 | 内容 |
| --- | --- |
| [安装](installation.md) | 安装 Python 包。 |
| [快速上手](quickstart.md) | 把配置生成为 STL 和 MJCF，看懂输出目录。 |
| [配置文件](config-file.md) | 参数、零件、形状、选项、打印组和相机，附一个完整例子。 |
| [坐标系](frames.md) | 坐标系树、默认工具的坐标系名称、求解坐标系。 |
| [检查与干涉规则](checks.md) | 生成器检查什么，不检查什么。 |
| [导出到 MuJoCo](mjcf.md) | MJCF 文件里有什么，怎样装到机械臂上。 |
| [网页编辑器](editor.md) | 在浏览器里配置、查看和导出。 |
| [Fusion 插件](fusion.md) | 把配置在 Autodesk Fusion 里生成为参数化设计，并原地更新。 |
| [真机环境](robot-setup.md) | 机械臂、两部手机和箱子；安装真机一侧的软件。 |
| [机械臂工具与安全规则](robot-arm-tools.md) | 真机的使用规则、程序出错时会怎样，以及每个工具。 |
| [标定](robot-calibration.md) | 在用的标定文件、写出它们的工具、标记、推杆实物的坐标系。 |
| [遥操作](teleoperation.md) | 用手持 iPhone 或 leader 臂带着机械臂动。 |
| [数据采集](data-collection.md) | episode、录制，以及导出成 LeRobot 数据集。 |
| [仿真](simulation.md) | 这套设备的 MuJoCo 场景，和 `--sim`。 |
| [排错](troubleshooting.md) | 常见提示信息和原因。 |

没有特别说明时，长度单位是毫米，角度单位是度。只有 MJCF 文件例外：MuJoCo 用米。
