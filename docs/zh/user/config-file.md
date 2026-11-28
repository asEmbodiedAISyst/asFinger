# 配置文件

一份配置就是一个 JSON 文件，描述一个工具的参数、坐标系和实体零件。这一页逐节说明文件的内容，最后给一个完整的例子。

## 各节内容

| 键 | 内容 |
| --- | --- |
| `name` | 工具的名字，也是 MJCF 文件里的模型名。 |
| `description` | 任意说明文字。 |
| `root` | 根坐标系的名字。没有另外说明时，所有输出都以它为基准。 |
| `params` | 有名字的数值和表达式。 |
| `param_notes` | 参数的备注，可有可无，生成器不读。 |
| `frames` | 坐标系树，见[坐标系](frames.md)。 |
| `parts` | 实体零件，每个零件绑在一个坐标系上。 |
| `shapes` | 起了名字的形状，可以被多个零件引用。 |
| `options` | 控制一组坐标系和零件的开关。 |
| `print_sets` | 合并成一个 STL 文件的几个打印件。 |
| `cameras` | 工具上的相机。 |
| `checks`、`interference` | 限制条件和干涉规则，见[检查与干涉规则](checks.md)。 |
| `references` | 只在预览里显示的网格，用来和实物对照。 |
| `mjcf` | 导出 MuJoCo 时的设置，见[导出到 MuJoCo](mjcf.md)。 |

长度单位毫米，角度单位度，密度单位 g/cm³。

## 参数与表达式

参数可以是数值，也可以是写成字符串的表达式。表达式里可以引用别的参数。

```json
"params": {
  "rod_D": 15,
  "rod_tilt": 30,
  "tip_R": "rod_D/2",
  "rod_embed": "rod_D/2*tand(rod_tilt) + 1"
}
```

其他各节里的数值大多也可以写成表达式，例如 `"pos": [0, 0, "base_t/2"]`。

表达式里可以出现：

- 数字和参数名；
- 运算符 `+ - * / // % **` 和括号；
- 比较（`<`、`<=`、`>`、`>=`、`==`、`!=`），结果是 1 或 0；
- 条件：`a if 条件 else b`；
- 常量 `pi`、`true`、`false`；
- 函数 `sin cos tan asin acos atan atan2`（弧度）、`sind cosd tand asind acosd atand atan2d`（角度）、`sqrt abs min max round radians degrees`。

别的 Python 语法一律报错。网页编辑器用同一套 Python 代码计算配置，两边结果相同。

## 零件

一个零件就是一个实体，有名字、所在的坐标系和一棵形状树（`csg`）。

```json
{
  "name": "tool_body", "frame": "F_mount", "role": "printed", "density": 1.24, "color": "#8a94a6",
  "csg": {"union": [ ... ]}
}
```

| 键 | 含义 |
| --- | --- |
| `name` | 零件在 `print/` 和 `meshes/` 里的文件名。 |
| `frame` | 形状树的起始坐标系。打印件的 STL 就写在这个坐标系里。 |
| `role` | `"printed"` 的零件会写进 `print/`。默认配置里还有 `"reference"`（手机）和 `"hardware"`（外购件）。 |
| `density` | 密度，g/cm³，用来算质量和惯量，默认 1.0。 |
| `color` | 十六进制颜色，用于预览、编辑器和 MJCF 文件。 |
| `enabled` | 表达式，值为 0 时不要这个零件。 |
| `mjcf` | 写 `false` 时这个零件不进 MJCF 文件。 |
| `collision` | 一组形状，代替自动生成的碰撞体写进 MJCF 文件。 |

## 形状

形状树由四种基本形状和两种运算组成。

| 形状 | 写法 |
| --- | --- |
| 长方体 | `{"box": {"size": [x, y, z]}}`，以自身原点为中心 |
| 两点之间的方杆 | `{"box": {"size": [w, t], "from": PT, "to": PT, "up": [x, y, z]}}` |
| 两个角点之间的长方体 | `{"box": {"corners": [PT, PT]}}`，各边沿节点的坐标轴 |
| 球 | `{"sphere": {"r": r}}` |
| 圆柱 | `{"cylinder": {"r": r, "h": h}}`，沿局部 Z 轴，以自身原点为中心 |
| 两点之间的圆柱 | `{"cylinder": {"r": r, "from": PT, "to": PT}}` |
| 导入的网格 | `{"mesh": {"file": "assets/x.stl", "scale": 1}}` |
| 并集 | `{"union": [节点, 节点, ...]}` |
| 差集 | `{"difference": [被减体, 减去的体, 减去的体, ...]}` |

`PT` 表示一个点，可以写成节点坐标系下的 `[x, y, z]`，也可以写成指定坐标系下的 `{"frame": "S_mount", "pos": [x, y, z]}`。用后一种写法，一个形状就能连接两个坐标系，参数变了它会跟着两头一起变。

两点之间的方杆和圆柱可以再加长：方杆用 `extend_from`、`extend_to`，两者都可以用 `extend`（毫米）。

每个节点还可以带这些键：

| 键 | 含义 |
| --- | --- |
| `name` | 节点的名字，干涉规则和测试靠它来指定节点。 |
| `pos`、`rot` | 节点在父节点坐标系里的位姿。`rot` 的写法见[坐标系](frames.md#旋转的写法)。 |
| `frame` | 把这个节点放到指定的坐标系里，而不是父节点的坐标系。 |
| `enabled` | 表达式，值为 0 时去掉这个节点。 |
| `needs` | 坐标系名字的列表。某个选项去掉其中任何一个坐标系时，这个节点也去掉，例如只有和支架横梁一起才有意义的腹板。 |
| `sim` | 只对基本形状有效：`"collide"`（默认）会成为 MuJoCo 碰撞体，`"none"` 不会。 |
| `color` | 这个节点的颜色。 |

导入的网格必须是封闭实体。`file` 里的路径相对于“配置所在目录的上一级目录”。在本仓库里，`hardware/configs/` 下的配置写 `assets/x.stl`，实际读的是 `hardware/assets/x.stl`。也可以写绝对路径。

### 共用的形状

一棵形状树要用在不止一处时，把它放到 `shapes` 下面：

```json
"shapes": {"connector_b": {"difference": [ ... ]}},
...
{"use": "connector_b", "frame": "F_adapter"}
```

`use` 节点可以有自己的 `name`、`pos`、`rot`、`frame` 和 `enabled`。

## 选项

选项用来关掉一组坐标系，连同依赖它们的所有内容。

```json
"options": {
  "phone": {"value": true, "modules": ["phone", "holder", "connector"],
            "desc": "Phone camera with its holder. Off = the rod alone."}
}
```

每个坐标系可以写一个 `module`。选项关掉后，生成器会去掉：

- 属于这些模块的坐标系，以及依赖它们的坐标系；
- 引用了这些坐标系、或在 `needs` 里写了它们的形状；
- 因此变空的零件，以及建立在这些坐标系上的相机、检查、对照模型和打印组成员。

被去掉的坐标系不再求解。配置文件里的内容原样保留。用 `--option phone=0` 或 `m.set_options(phone=False)` 开关选项。

## 打印组

打印组把几个打印件合并成一个 STL 文件：

```json
"print_sets": {"ipush_print": ["tool_body", "holder"]}
```

输出文件是 `print/ipush_print.stl`，坐标在列表里第一个零件的坐标系里。`report.json` 给出每个打印组的实体个数。要作为一个整体打印的打印组应该只有 1 个实体；个数更多，说明零件之间没有连上。

## 相机

相机的名字就是某个坐标系的名字，位姿由这个坐标系给出。

```json
"cameras": {
  "C_main": {"fovy_deg": "2*atand(sqrt(36**2 + 24**2)*0.6/2/feq)", "aspect": "4/3",
             "resolution": [640, 480], "min_focus_mm": null}
}
```

`fovy_deg` 是竖直方向的视场角，`aspect` 是宽高比（默认 4/3），`resolution` 会写进 MJCF 文件。`min_focus_mm` 填了数值之后，相机到目标的距离小于它时求解器会给出警告。

默认配置里的相机数据有这些局限：

- 所有相机的 `min_focus_mm` 都是 `null`，因为 Apple 没有公布最近对焦距离，所以对焦检查是关着的。
- `C_main` 和 `C_tele` 的视场角是按等效焦距算的，没有实测。`C_ultrawide` 的数值是在 iPhone 17 Pro 上对焦无穷远时实测的；编辑器里的其它手机也沿用它，它们的超广角同样是 13 mm。
- 前置相机 `C_front` 的位姿是估计值，见[坐标系](frames.md#默认工具的坐标系)。

## 一个完整的例子

这份配置是一个圆盘底座、一根倾斜的杆和一个球头。把它存成 `my_tool/configs/minimal_rod.json`。

```json
{
  "name": "minimal_rod",
  "root": "F_robot",
  "params": {
    "base_R": 25,
    "base_t": 8,
    "rod_D": 15,
    "rod_L": 120,
    "rod_tilt": 20,
    "tip_R": "rod_D/2"
  },
  "frames": {
    "F_robot": {"parent": null, "desc": "Robot flange: origin on the flange face, +Z out of the flange."},
    "R_rod": {"parent": "F_robot", "pos": [0, 0, "base_t"], "rot": {"axis": [0, 1, 0], "deg": "rod_tilt"},
              "desc": "Rod axis. +Z points to the tip."},
    "T_tip": {"parent": "R_rod", "pos": [0, 0, "rod_L"], "desc": "Centre of the ball tip."},
    "T_tcp": {"parent": "T_tip", "pos": [0, 0, "tip_R"], "desc": "Apex of the ball tip."}
  },
  "parts": [
    {
      "name": "rod", "frame": "F_robot", "role": "printed", "density": 1.24, "color": "#8a94a6",
      "csg": {"union": [
        {"name": "base", "cylinder": {"r": "base_R", "h": "base_t"}, "pos": [0, 0, "base_t/2"]},
        {"name": "shaft", "cylinder": {"r": "rod_D/2", "from": {"frame": "R_rod", "pos": [0, 0, -3]}, "to": {"frame": "T_tip"}}},
        {"name": "tip", "sphere": {"r": "tip_R"}, "frame": "T_tip"}
      ]}
    }
  ],
  "checks": [
    {"frame": "T_tcp", "axis": "z", "min": 60, "msg": "The tip is too close to the flange: make rod_L longer or rod_tilt smaller."}
  ]
}
```

生成：

```bash
asfinger build my_tool/configs/minimal_rod.json -o out/minimal_rod
```

输出有 `print/rod.stl`、`meshes/rod.stl`、`ipush_tool.xml`、`preview.html`、`resolved.json` 和 `report.json`，报告里的质量是 46.8 g。这份配置没有相机 `C_main`，所以 `preview.html` 是空白的（见[快速上手](quickstart.md#输出文件)）。

再把杆倾斜到检查不通过：

```bash
asfinger frames my_tool/configs/minimal_rod.json --set rod_tilt=70
```

```text
T_tcp     pos=[119.81, 0.0, 51.61]  z=[0.94, 0.0, 0.342]  module
[check] The tip is too close to the flange: make rod_L longer or rod_tilt smaller. (T_tcp.z = 51.61, allowed 60.0 .. )
```
