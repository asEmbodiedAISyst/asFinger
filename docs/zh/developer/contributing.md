# 构建、测试与贡献

这一页说明怎样搭好环境、要跑哪些检查，以及文档是怎么构建的。

## 搭环境

Python 包用 [uv](https://docs.astral.sh/uv/) 管理，网站需要 Node.js 22 或更高版本。

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
uv sync                      # 包和开发工具
cd site && npm ci            # 网站
```

## 包的检查

在仓库根目录运行下面的命令，必须全部通过。

```bash
uv run ruff check
uv run ruff format --check
uv run pytest
```

`uv run ruff format` 用来整理格式。测试会生成 `hardware/configs/` 里的配置，并把结果加载到 MuJoCo 里；还会生成文档里的例子，并比较两种语言的页面清单。`asfinger send` 和 Fusion 插件的测试用的是本机的 HTTP 服务和 `adsk` 模块的替身，不会启动 Fusion，所以改了 `hardware/cad/fusion/` 之后还要在 Fusion 里手工试一遍。

`tests/robot/` 里的测试在仿真里运行真机一侧的工具。它们需要 `robot` 依赖组，没装这个组时会被跳过：

```bash
uv sync --group robot --python 3.12
uv run --group robot pytest tests/robot
```

没有任何测试会去连接机械臂或手机。对 `robot/` 的修改只要可能影响运动，就还得由这套设备的负责人在真机上跑一遍，旁边要有人守着电源开关。在 pull request 里写明哪些在真机上跑过、哪些没有。需要 `calibration/data/` 里的原始标定数据或真实场景照片的测试，只在有这些文件的地方运行。需要机械臂网格（`uv run python sim/fetch_arm_meshes.py`）或 GL 上下文的测试也是这样：把 `ASFINGER_TEST_GL` 设成一个 MuJoCo 的 GL 后端（比如 macOS 上的 `glfw`），渲染测试才会运行。

修改生成器时，把修改前后的输出对比一下。不打算改变几何的修改，STL 文件和 `ipush_tool.xml` 必须逐字节相同：

```bash
uv run asfinger build hardware/configs/iphone17pro_default.json -o out/after
```

## 网站

```bash
cd site
npm run dev        # 先同步，再启动开发服务器 http://localhost:4321
npm run build      # 先同步，再把静态网站生成到 site/dist
npm run preview    # 预览 site/dist
```

每次构建之前，`npm run sync` 会运行两个脚本：

- `scripts/sync-core.mjs` 把 `src/asfinger` 里纯 Python 的模块、`hardware/configs` 里的配置、配置引用的网格和 Pyodide 运行时复制到 `site/public/`。
- `scripts/sync-docs.mjs` 把文档复制到 Starlight 的内容目录，并生成 `llms.txt` 和 `llms-full.txt`。

这些副本都是生成的，git 不跟踪，不要去改它们。

`hardware/configs/` 里的每一份配置都会随网站一起发布，配置引用的网格也一样。

网站地址和基础路径由两个环境变量决定，部署时会设置好。想在本机按发布后的路径测试：

```bash
SITE_URL=https://asembodiedaisyst.github.io BASE_PATH=/asFinger/ npm run build
```

编辑器的界面文字在 `site/src/i18n/index.ts` 里。产品名只在那里定义一次（`PRODUCT`、`EDITOR_NAME`）。

## 文档

文档源文件在 `docs/en/` 和 `docs/zh/`，两棵目录树的文件一一对应，各有 `user/`、`developer/`、`agents/` 三部分。

规则：

- 两种语言一起改。两边的页面不一致时，测试不通过。
- 每种语言按自己的习惯来写，不要逐句对译。
- 用[术语表](../glossary.md)里的术语。新术语要在两种语言的术语表里都加上。
- 每页以一个 `# 标题` 开头，后面跟一小段话。网站把它们用作页面标题和描述。
- 链接到别的页面时，用指向 `.md` 文件的相对链接，构建网站时会自动转换。
- 缺陷和风险写在它所属功能的那一页上。
- 内部笔记放在 `docs/internal/`，这个目录被 git 忽略。公开页面里不要引用它。

新增页面时，还要在 `site/scripts/sync-docs.mjs` 的 `ORDER` 列表里加一项，它决定侧边栏里的顺序。

## 持续集成

| Workflow | 触发 | 作用 |
| --- | --- | --- |
| `.github/workflows/ci.yml` | 推送到 `main`、pull request | 在每个支持的 Python 版本上运行 ruff 和 pytest，在一个 Python 版本上运行仿真里的真机工具测试，并构建网站。 |
| `.github/workflows/pages.yml` | 推送到 `main`，且改动涉及网站、文档、包或硬件输入 | 构建网站并部署到 GitHub Pages。 |

## 提交修改

1. 新建分支。
2. 完成修改，新行为要有测试。
3. 两种语言的文档一起更新。
4. 运行包的检查；改动涉及网站、文档、包或配置时，再在 `site/` 里运行 `npm run build`。
5. 发起 pull request，写清楚改了什么，默认配置的输出有没有变。

注释和 docstring 一律用英文。
