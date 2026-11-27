# 修改本仓库

这一页写给修改本仓库的代码、网站或文档的 agent。

## 规则

- 注释和 docstring 一律用英文。
- `geom.py`、`expr.py`、`frames.py`、`csg.py`、`options.py`、`interference.py`、`mjcf.py` 和 `__init__.py` 在模块顶层只能导入标准库。浏览器要在 Pyodide 里运行这些文件。
- 改了 `src/asfinger/mesh.py` 里生成实体的方式，就在 `site/src/engine/csg.ts` 里做同样的修改。反过来也一样。
- 不要改这些名称，它们属于文件格式或已存储的数据：`ipush_tool.xml`、`ipush_print`、MJCF 的 body `ipush`、class `ipush_col` 和 `ipush_vis`、local storage 的键 `ipush.editor.v3` 和 `ipush.theme`、坐标系名称、配置的键和配置文件名、HTTP 路径 `/ipush/apply`、端口 47910、健康检查回复里的 `ipush-fusion`，以及 Fusion 设计里的属性组 `ipush` 和它的键。
- 产品名只在两处改：`PRODUCT_NAME`（`src/asfinger/__init__.py`），以及 `PRODUCT` 和 `EDITOR_NAME`（`site/src/i18n/index.ts`）。
- 如果一项修改不打算改变几何，就在修改前后各生成一次默认配置，确认每个 STL 文件和 `ipush_tool.xml` 完全相同。
- 不要手工修改求解坐标系里存着的 `result`。运行 `asfinger build CONFIG -o OUT --resolve`。
- 改了 `docs/en/` 里的页面，就在 `docs/zh/` 里做对应的修改。反过来也一样。中文按中文的习惯写，不要逐句翻译。
- 不要修改生成的文件：`site/public/py`、`site/public/configs`、`site/public/assets`、`site/public/pyodide`、`site/public/docs`、`site/public/zh`、`site/public/llms.txt`、`site/public/llms-full.txt`、`site/src/content/docs`。
- 不要提交 `docs/internal/` 里的文件，公开页面里也不要链接到它们。
- `hardware/configs/` 里的每个文件都会随网站发布。除非用户要求，不要往里面加配置。
- 引入第三方材料时必须带上它的许可证，并记入 `NOTICE`。
- 版本号只在 `pyproject.toml` 里改。
- `hardware/cad/fusion/` 里的代码在 Autodesk Fusion 里运行。不要为了测试去启动 Fusion、加载插件或改动 Fusion 文档。运行测试，然后请用户在 Fusion 里试。
- `robot/` 里的代码会让真实的机械臂动起来。在 agent 会话里，除非操作者就在机械臂旁边并且明确要求，否则不要运行任何会连接真机或手机的命令。带 `--sim` 的命令可以随时运行。
- 不要重构 `robot/`。只要修改可能影响运动，就需要这套设备的负责人在真机上跑一遍。在报告里写明哪些在仿真里跑过，并说明没有在真机上运行。
- 不要把这套设备的地址、设备号或主机名写进被 git 跟踪的文件，它们应该放在 `robot/cameras.local.yaml` 里。不要提交 `calibration/data/` 和 `data/` 里的文件，也不要添加设备的照片。
- `robot/arm_sign_check.py` 和 `robot/arm_listen_ab.py` 一启动就连接机械臂，加 `--help` 也一样。想看用法就读它们的 docstring，不要去运行。
- 不要推送 tag，不要改部署设置。把该做的事告诉用户。

## 代码地图

| 路径 | 内容 |
| --- | --- |
| `src/asfinger/__init__.py` | `Model`：加载、改参数、解算、检查、干涉、生成。`PRODUCT_NAME`。 |
| `src/asfinger/__main__.py` | 命令行（`build`、`frames`、`send`）。 |
| `src/asfinger/expr.py` | 参数表达式。 |
| `src/asfinger/frames.py` | 坐标系树和求解器。 |
| `src/asfinger/csg.py` | 形状树。 |
| `src/asfinger/options.py` | 选项。 |
| `src/asfinger/interference.py` | 干涉规则。 |
| `src/asfinger/mesh.py` | 实体、STL、质量（numpy、manifold3d）。 |
| `src/asfinger/mjcf.py`、`preview.py`、`build.py` | 写各种输出文件。 |
| `tests/test_default.py` | 针对 `hardware/configs/` 里配置的测试。 |
| `tests/test_docs.py` | 文档的测试：两种语言页面一致，例子配置能生成。 |
| `tests/test_send.py`、`tests/test_fusion_addin.py` | `asfinger send` 的测试，以及用 `adsk` 模块的替身对 Fusion 插件做的测试。 |
| `hardware/configs/`、`hardware/assets/` | 配置和它们引用的网格。 |
| `robot/` | 真机用的脚本。`arm` 是 rebot-control 的包装；`arm_*.py` 是机械臂工具和标定；`teleop*.py` 是遥操作；`episode.py`、`record.py`、`to_lerobot.py` 管数据；`snapshot.py`、`tags.py`、`make_tags.py`、`calibrate_color.py` 管相机和标记。 |
| `calibration/` | 工具要读的标定文件。`calibration/data/` 是本地目录，git 忽略它。 |
| `sim/` | MuJoCo 场景（`scene.py`、`scene.yaml`）和它的配准（`register.py`、`registration.yaml`）。 |
| `tests/robot/` | 真机一侧在仿真里的测试，需要先 `uv sync --group robot`。 |
| `hardware/cad/fusion/` | Fusion 插件（`asFingerAddIn`）、脚本（`asFingerFromJSON`）和两者共用的模块（`asfinger_fusion`）。每个目录里，目录名、`.py` 文件名和 `.manifest` 文件名必须相同。 |
| `site/scripts/sync-core.mjs`、`sync-docs.mjs` | 构建前把包、配置和文档复制进网站。 |
| `site/src/engine/` | web worker（Pyodide 和 Manifold）。 |
| `site/src/editor/`、`site/src/data/`、`site/src/i18n/` | 编辑器、它的目录数据、它的文字。 |
| `site/src/pages/`、`site/src/components/` | 首页和编辑器页面。 |
| `site/astro.config.mjs` | 网站地址、基础路径、Starlight 侧边栏。 |
| `docs/en/`、`docs/zh/` | 文档源文件。 |
| `.github/workflows/` | CI 和网站部署。 |

## 检查

结束之前运行下面的命令，必须全部通过。

```bash
uv run ruff check
uv run ruff format --check
uv run pytest
```

改动涉及 `site/`、`docs/`、`src/asfinger/` 或 `hardware/` 时，再运行：

```bash
cd site && npm ci && npm run build
```

如果改动涉及 `robot/`、`sim/` 或 `calibration/`，还要运行：

```bash
uv sync --group robot --python 3.12 && uv run --group robot pytest tests/robot
```

## 常见任务

### 给配置加一个参数

1. 在配置的 `params` 里加上参数，并在某个坐标系或形状里用到它。
2. 如果求解器用到它，运行 `uv run asfinger build CONFIG -o out/x --resolve`，把新结果存下来。
3. 如果编辑器里要显示它，在 `site/src/data/pusherParams.ts` 里加一项，标签写中英文。
4. 在 `tests/test_default.py` 里新增或修改测试。
5. 运行检查。

### 增加一种形状或一种坐标系写法

1. 在 `csg.py` 或 `frames.py` 里加上解算逻辑。
2. 如果是新的基本形状，还要加到 `mesh.py`、`mjcf.py` 和 `site/src/engine/csg.ts` 里。
3. 在 `docs/en/user/config-file.md` 或 `frames.md` 里说明，中文页面同步修改。
4. 加测试。运行检查并构建网站。

### 增加一条干涉规则

1. 在配置的 `interference` 里加上规则，写好 `id`、`msg`（中文）和 `msg_en`。
2. 加两个测试：一个让规则不通过，一个确认默认配置通过。
3. 把规则加进 `docs/en/user/checks.md` 和 `docs/zh/user/checks.md` 的表里。

### 增加一个文档页面

1. 在 `docs/en/` 和 `docs/zh/` 里用相同的文件名新建页面。
2. 把文件名加进 `site/scripts/sync-docs.mjs` 的 `ORDER`。
3. 在两种语言里，都从所属部分的索引页链接到新页面。
4. 运行 `uv run pytest` 和 `cd site && npm run build`。

### 修改编辑器里的文字

1. 修改 `site/src/i18n/index.ts` 里对应的条目，中英文都改。
2. 目录条目和参数标签在 `site/src/data/catalog.ts` 或 `pusherParams.ts` 里改。
3. 运行 `cd site && npm run build`。

### 发布一个版本

1. 修改 `pyproject.toml` 里的 `version`。
2. 运行检查。
3. 告诉用户去创建 tag。不要自己推送 tag。
