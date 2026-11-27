# 快速上手

这一页生成默认工具，并说明每个输出文件是什么。

## 生成一个配置

在仓库根目录运行：

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/iphone17pro_default
```

命令打印一份报告，并写出这个目录：

```text
out/iphone17pro_default/
├── print/
│   ├── ipush_print.stl    推杆和手机支架合成的一个实体
│   ├── tool_body.stl      只有推杆
│   └── holder.stl         只有手机支架
├── meshes/                每个零件一个 STL，供 MJCF 文件使用
├── ipush_tool.xml         MuJoCo 模型
├── preview.html           在浏览器里看的三维预览
├── resolved.json          所有坐标系和形状，数值都已算好
└── report.json            体积、质量和检查结果
```

`ipush_print.stl` 和 `ipush_tool.xml` 这两个文件名来自项目以前的名字。为了不影响已有的工具，文件名没有改。

## 输出文件

| 文件 | 内容 |
| --- | --- |
| `print/<零件>.stl` | 每个 `"role": "printed"` 的零件一个文件，坐标在该零件自己的坐标系里。 |
| `print/<打印组>.stl` | 每个打印组一个文件，组里的零件合成一个实体。默认配置里，推杆底座的安装面在 z = 0，打印时让这个面贴床。 |
| `meshes/<零件>.stl` | 所有零件，坐标在 MJCF body 的坐标系里。 |
| `ipush_tool.xml` | 碰撞体、视觉网格、质量和惯量，每个坐标系一个 site，还有相机。见[导出到 MuJoCo](mjcf.md)。 |
| `preview.html` | 零件、坐标系、碰撞体，以及相机 `C_main` 看到的画面。 |
| `resolved.json` | 给其他程序用：坐标系写成位置加四元数，形状树里的尺寸都是数值。 |
| `report.json` | 每个零件的体积、质量、三角形数；每个打印组的实体个数；总质量；没通过的干涉规则。 |

STL 是二进制格式，单位毫米。

> **预览的限制。** `preview.html` 从 CDN 加载 three.js，所以要联网。页面还要求配置里有名为 `C_main` 的相机；没有这个相机时（例如加了 `--option phone=0`），页面是空白的。

> **输出里有本机路径。** `resolved.json` 的 `base_dir` 字段记着存放 `configs/` 和 `assets/` 的那个目录的绝对路径。把文件发给别人之前先删掉这个字段。

## 改一个参数

用 `--set` 在这一次生成里改参数，配置文件本身不变。

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/short --resolve --set rod_L=160 --set rod_tilt=25
```

手机的位姿是求解坐标系：求解器根据杆和相机把它算出来，配置里存着上一次的结果。只要改了求解器用到的参数，就要加 `--resolve`。不加的话，生成时用的还是存着的旧位姿，并给出这条警告：

```text
[warn] P_phone: saved result is stale (inputs changed); run with --resolve to update
```

只写 `--resolve`、不带 `--set` 和 `--option` 时，新的结果还会写回配置文件。见[坐标系](frames.md#求解坐标系)。

## 开关一个选项

选项可以关掉一组坐标系和零件。下面的命令只生成推杆，不要手机和支架：

```bash
asfinger build hardware/configs/iphone17pro_default.json -o out/rod_only --option phone=0
```

## 列出坐标系

```bash
asfinger frames hardware/configs/iphone17pro_default.json
```

每行是一个坐标系：名称、在根坐标系里的位置、Z 轴方向，以及位姿的来源（`module` 或 `solved`）。

## 在 Python 里使用

```python
from asfinger import Model

m = Model.load('hardware/configs/iphone17pro_default.json')
for length in (140, 160, 180):
    m.copy().set(rod_L=length).build(f'out/rod_{length}', resolve=True)
```

常用调用：

| 调用 | 结果 |
| --- | --- |
| `Model.load(path)` | 从配置文件得到一个模型。 |
| `m.set(name=value)` | 改参数。名字不存在时抛出 `KeyError`。 |
| `m.set_options(phone=False)` | 开关选项。 |
| `m.frames(resolve=False)` | `(world, local, info)`：每个坐标系在根坐标系里和在父坐标系里的位姿。 |
| `m.root_to('T_tcp')` | 某个坐标系在根坐标系里的位姿，可以直接当作机械臂上的 TCP 偏移。 |
| `m.check()` | 没通过的检查的提示信息，空列表表示全部通过。 |
| `m.interference()` | 没通过的干涉规则的提示信息。 |
| `m.build(out_dir, resolve=False)` | 写出全部输出，返回解算后的模型和报告。 |

位姿对象有属性 `p`（位置，3 个数）和 `R`（旋转矩阵），以及方法 `quat()`（`[w, x, y, z]`）。

## 其他配置

| 配置 | 工具 |
| --- | --- |
| `iphone17pro_default.json` | iPhone 17 Pro 配 reBot Arm B601-RS 的推杆，装在机械臂的夹爪连接件上。 |
| `rebot_rs_flange.json` | 同一根推杆，不用安装转接件，底座直接用螺钉装在 reBot 第 6 关节的转子上。 |
| `pad_finger.json` | 指腹推杆：22 × 22 方杆加 R15 指腹，一体打印。`--set tip_split=1` 把指尖单独做成一个用 TPU 打印的实体（`tip_tpu`）；`--option tactile=1` 加上 48 × 48 电子皮肤的凹槽、FPC 槽和读出板及其盖板。其余和 `iphone17pro_default.json` 相同。 |
| `square_rod.json` | 更早的方杆推杆：10 × 10 mm 方杆、平头（编辑器里的“方杆推杆”）；其余和 `iphone17pro_default.json` 相同，只是手机支架没有背部加强。 |
