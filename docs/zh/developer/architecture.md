# 架构

生成器是一条流水线：输入只有一份配置，输出有好几种。网页编辑器在浏览器里运行的是同一条流水线的前半段。

## 流水线

```text
配置（JSON）
   │  expr.py        计算参数
   │  options.py     去掉关着的选项对应的坐标系和零件
   │  frames.py      解算坐标系树，运行求解器
   │  csg.py         解算每棵形状树：每个基本形状得到根坐标系下的位姿和数值尺寸
   ▼
解算后的模型        （到这里为止都是纯 Python：不用 numpy，不用本地扩展）
   │  mesh.py        用 manifold3d 生成实体并清理，读写 STL，计算质量属性
   │  interference.py  选出每条规则要比较的实体，由 mesh.py 求交
   ▼
build.py            写出 resolved.json、print/*.stl、meshes/*.stl、ipush_tool.xml（mjcf.py）、preview.html（preview.py）、report.json
```

对外的入口是 `__init__.py` 里的 `Model`，命令行在 `__main__.py`。

| 模块 | 作用 | 依赖 |
| --- | --- | --- |
| `geom.py` | 向量、旋转矩阵、四元数和变换类 `Tf`。 | 标准库 |
| `expr.py` | 用 `ast` 模块安全地计算参数表达式。 | 标准库 |
| `frames.py` | 坐标系树、旋转的几种写法、`pos_from`、`z_from`、求解器 `coplanar_look_at`、判断结果是否过期的哈希。 | `geom`、`expr` |
| `options.py` | 选项关掉后，配置被裁剪出来的视图。 | 标准库 |
| `csg.py` | 形状树：解算、碰撞用的基本形状、输出 JSON。 | `geom`、`expr`、`frames` |
| `interference.py` | 干涉规则：决定哪些解算后的形状树要求交。 | `geom`、`expr`、`csg` |
| `mjcf.py` | 写 MJCF。 | `expr` |
| `mesh.py` | 实体、STL 读写、质量和惯量。 | numpy、manifold3d |
| `preview.py` | HTML 预览。 | numpy |
| `build.py` | 把各步串起来并写文件。 | 以上全部 |

## 解算后的模型

`Model.resolve()` 返回一个字典：

| 键 | 内容 |
| --- | --- |
| `P` | 所有参数的数值。 |
| `world`、`local` | 每个坐标系在根坐标系里和在父坐标系里的位姿（`Tf`）。 |
| `info` | 每个坐标系的来源（`module`、`manual` 或 `solved`）和求解器的报告。 |
| `parts` | 各个零件，带着解算后的形状树和碰撞用的基本形状。 |
| `cfg` | 实际参与计算的配置：有选项关掉时，是裁剪后的视图。 |

解算后的基本形状有类型、数值尺寸和根坐标系下的位姿 `T`。所有后端读的都是这一个结构：网格生成、MJCF 输出、干涉规则，还有浏览器。`Model.resolved_json()` 是同样的数据，只是写成普通 JSON，位姿用位置加四元数表示。

## 求解器与过期结果

求解坐标系存着 `solve`（设计意图）和 `result`（位姿，外加求解器输入的哈希）。`resolve_frames` 每次运行都重新算一遍哈希；除非传了 `resolve=True`，否则用存着的结果，哈希对不上就报告结果已过期。这样生成是可重复的：同一份配置文件总是得到同样的输出，即使以后求解器的代码改了也一样。

## 浏览器

`site/` 里的编辑器运行流水线里纯 Python 的那一半，网格后端换成了另一套。

```text
site/scripts/sync-core.mjs      把 src/asfinger/*.py（纯 Python 的模块）、hardware/configs/*.json 和它们引用的网格
                                复制到 site/public/，再从 node_modules 复制 Pyodide 运行时
site/src/engine/worker.ts       web worker：Pyodide 导入 asfinger，返回 resolved_json、检查的提示信息，
                                以及带着新求解结果的配置
site/src/engine/csg.ts          用 manifold-3d（WebAssembly）生成解算后的形状树；和 mesh.py 一一对应
site/src/engine/client.ts       主线程一侧的句柄；只保留最新的一次求解请求
site/src/editor/                React 界面和 three.js 视图
site/src/data/                  载体、转接件、相机的目录，以及参数的标签
```

`sync-core.mjs` 里的 `PURE` 列表写着要复制哪些模块，列表里的模块不能导入 numpy 或 manifold3d。干涉规则以解算后的形状树的形式放在 `resolved_json` 里传给浏览器，由 `worker.ts` 求交。

`csg.ts` 和 `mesh.py` 是同一步的两份实现，改了一处，另一处也要改。

## 文档站

`site/scripts/sync-docs.mjs` 把 `docs/en` 和 `docs/zh` 复制到 Starlight 的内容目录，改写页面之间的链接，并生成 `llms.txt` 和 `llms-full.txt`。首页和编辑器是 `site/src/pages` 里的普通 Astro 页面。见[构建、测试与贡献](contributing.md#文档)。

## Fusion 插件

`hardware/cad/fusion/` 里是第三个后端。`asFingerAddIn` 在 Autodesk Fusion 里用 Fusion 自带的 Python 运行，把仓库的 `src/` 加进导入路径，只用到管线里纯 Python 的那一半：`Model.resolve`、`Model.check` 和 `Model.resolved_json`。`asfinger_fusion.py` 把解算后的形状树变成 Fusion 的特征，并给每个特征打上属性标记，下一次运行就能在原地改同一批特征。脚本 `asFingerFromJSON` 把一份 `resolved.json` 交给同一个模块，不导入 `asfinger` 包。

`asfinger send` 命令和插件之间走 127.0.0.1:47910 上的 HTTP。Fusion 的 API 只能在一个线程里调用，所以请求通过自定义事件转交给 Fusion 的主线程。`tests/test_fusion_addin.py` 用替身代替 `adsk` 模块来导入插件。见 [Fusion 插件](../user/fusion.md)。

## 真机一侧

`robot/`、`calibration/` 和 `sim/` 是仓库的第二部分。它们不导入 `asfinger` 包，`asfinger` 包也不导入它们。两部分之间靠数据衔接：工具文件 `calibration/tool_ip17pro_print.yaml` 是按生成器给出的推杆实物坐标系写的，`sim/assets/meshes/ipush_print.stl` 是生成器的打印输出。

```text
robot/*.py            脚本，在仓库根目录下运行，彼此按文件名导入
   │  rebot_control   控制库（从 GitHub 取的依赖）：伺服循环、各种限制、笛卡尔控制、仿真器
   │  imuninn         手机：视频流和 IMU 流
   ▼
calibration/*.yaml    一台机械臂和一个工具的增益与模型；工具读它们，其中几个工具也写它们
sim/scene.py          MuJoCo 场景；工具加 `--sim` 后，同一份代码跑在 rebot-control 的仿真电机上
sim/twin.py           孪生场景：同一台仿真机械臂，加上网格、封闭的箱子、灯光和相机色调
data/episodes/        录制工具写出的数据（不进 git）
```

- `robot/teleop.py` 是遥操作里机械臂这一侧的逻辑，`teleop_iphone.py` 和 `teleop_star.py` 给它提供指令来源。
- `robot/episode.py` 负责录制和读取 episode，`record.py` 加上按键，`to_lerobot.py` 做转换。
- `robot/snapshot.py` 里的 `camera()` 是唯一知道手机在哪的函数，它读 `robot/cameras.local.yaml`，这个文件不进 git。
- `sim/twin.py` 根据 `sim/twin.yaml`、工具文件里的 `sim:` 段和 `sim/twin_registration.yaml` 搭出孪生场景。机械臂网格由 `sim/fetch_arm_meshes.py` 下载，不进 git。`sim/twin_filament.py` 是可选的第二个渲染器。
- 这些脚本依赖 `pyproject.toml` 里的 `robot` 组，持续集成的其他任务不安装它。

这部分代码会让真实的机械臂动起来。导入时没有改动它的控制流程；会要求改代码的 `ruff` 规则，对 `robot/` 是关掉的。见[机械臂工具与安全规则](../user/robot-arm-tools.md)。

## 沿用旧项目名的名称

项目在改名为 asFinger 之前叫 iPush。下面这些名称属于文件格式或已存储的数据，所以没有改：输出文件 `ipush_tool.xml` 和 `ipush_print.stl`，打印组的名字 `ipush_print`，MJCF 里的 body `ipush` 和 class `ipush_col`、`ipush_vis`，local storage 的键 `ipush.editor.v3` 和 `ipush.theme`，导出的配置文件名，`send` 命令用的路径 `/ipush/apply` 和端口 47910，Fusion 插件健康检查回复里的名字 `ipush-fusion`，以及 Fusion 设计里的属性组 `ipush` 和它的键（插件靠它们找到已有设计里的特征）。真机一侧，网格 `sim/assets/meshes/ipush_print.stl`、工具文件名 `tool_ip17pro_print.yaml`、episode 里的字段和任务名都属于数据名称，没有改。环境变量换了新名字（`ASFINGER_TOP_CAM`、`ASFINGER_WRIST_CAM`、`ASFINGER_TEST_ABORT`），以 `IPUSH_` 开头的旧名字仍然有效。给人看的名字只定义两处：Python 包里的 `PRODUCT_NAME`，网站里的 `PRODUCT` 和 `EDITOR_NAME`（`site/src/i18n/index.ts`）。
