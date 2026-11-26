# 坐标系

坐标系是这个工具对外的接口。机械臂法兰、TCP、手机和每个相机，都是同一棵树里有名字的坐标系。每种输出都带着它们的位姿，所以机器人程序、仿真和打印出来的零件用的是同一套数。

## 约定

- 每个坐标系有父坐标系、位置和旋转。根坐标系写 `"parent": null`。
- 位姿把子坐标系里的坐标变到父坐标系：`x_parent = R · x_child + p`。
- 位置单位毫米。四元数是 `[w, x, y, z]`，和 MuJoCo 的顺序一样。
- 所有输出里的位姿都写成位置加四元数。

## 坐标系的写法

```json
"R_rod": {"parent": "F_tool", "pos": ["rod_x", 0, 0], "rot": {"axis": [0, 1, 0], "deg": "rod_tilt"},
          "module": "rod", "desc": "Rod axis at the adapter face; +Z along the rod toward the tip."}
```

`module` 把坐标系归到某一组，选项可以整组关掉。`desc` 是说明文字。

### 旋转的写法

| 写法 | 含义 |
| --- | --- |
| `{"axis": [x, y, z], "deg": a}` | 绕某根轴转 `a` 度。角度是参数时用它最方便。 |
| `{"quat": [w, x, y, z]}` | 四元数。 |
| `{"xyaxes": [x0, x1, x2, y0, y1, y2]}` | 子坐标系的 X 轴和 Y 轴在父坐标系里的方向。 |
| `{"mat": [9 个数]}` | 旋转矩阵，按行写。它的各列是子坐标系的轴在父坐标系里的方向。 |
| 上面几种组成的列表 | 按顺序依次旋转，每一步都在上一步得到的坐标系里进行。 |

### 位置取自另一个坐标系

坐标系的原点可以取另一个坐标系里的一个点。这个点还可以沿某个方向滑动，直到碰到一个平面。

```json
"J_foot": {"parent": "F_tool",
           "pos_from": {"frame": "S_mount", "pos": [0, 0, "-plate_t/2"], "dir": [-1, 0, 0],
                        "until": {"frame": "F_tool", "axis": "x", "value": "beam_x"}}}
```

这个坐标系从 `S_mount` 下方的一个点出发，沿 `S_mount` 的 −X 方向移动，直到它在 `F_tool` 里的 X 坐标等于 `beam_x`。写 `"use": "xy"` 时只有这两个坐标取自这个点，其余的取 `pos`。

### 朝向取自几个方向

`z_from` 把 Z 轴定为几个方向之和，这些方向各自在别的坐标系里给出。两个方向相加得到的是它们的角平分线。`x_hint` 让 X 轴尽量靠近某个方向。

```json
"J_bend": {"parent": "F_tool", "pos_from": {"frame": "J_foot"},
           "z_from": [{"frame": "F_tool", "dir": [0, 0, 1]}, {"frame": "S_mount", "dir": [1, 0, 0]}],
           "x_hint": {"frame": "F_tool", "dir": [0, 1, 0]}}
```

## 求解坐标系

求解坐标系不写固定位姿，只写设计意图（`solve`）。位姿由求解器算出来，存在配置的 `result` 里。

```json
"P_phone": {"parent": "F_tool",
            "solve": {"type": "coplanar_look_at", "target": "T_tcp", "axis_frame": "R_rod", "camera": "C_main",
                      "plane_angle_deg": "phone_flange_angle", "v_n": "v_n", "distance_mm": "distance",
                      "image_up": "away_from_flange"},
            "result": {"pos": [...], "quat": [...], "solve_hash": "18a43136b678"}}
```

目前只有一种求解器 `coplanar_look_at`。它摆放手机时满足：

- `camera` 的光轴落在法兰轴线和杆轴线所在的平面内；
- 光轴和法兰轴线的夹角是 `plane_angle_deg`；
- `target` 出现在画面水平方向的正中，高度是 `v_n`（−1 是底边，0 是中心，+1 是顶边）；
- 镜头到 `target` 的距离是 `distance_mm`；
- 画面的上方朝向法兰或背向法兰（`image_up`：`toward_flange` 或 `away_from_flange`）。

`camera` 必须是求解坐标系的直接子坐标系。

生成时用的始终是存着的 `result`。生成器会把求解器输入的哈希和存着的哈希比一下。两者不同，说明结果已经过期，生成器给出警告，但不会替换结果。

> **结果过期会得到错误的几何。** 这时手机、支架和检查用的是旧位姿，杆用的却是新参数。只要改了求解器用到的参数（杆、末端、相机位置，以及 `phone_flange_angle`、`v_n`、`distance` 这三个参数），就要加 `--resolve`。

`--resolve` 让求解器重新算一遍。不带 `--set` 和 `--option` 时，新结果还会写回配置文件。网页编辑器每次都重新求解。

## 默认工具的坐标系

默认配置 `iphone17pro_default.json` 的坐标系树：

```text
F_robot                 机械臂法兰，按机械臂自己的定义（根）
├── F_adapter           法兰转接件（位姿和 F_robot 相同）
└── F_mount             推杆底座的安装面
    └── F_tool          底座板朝工具一侧的面
        ├── R_rod       杆的轴线，+Z 指向末端
        │   └── T_tip   杆端面的中心
        │       └── T_tcp   末端的顶点，接触参考点
        ├── P_phone     手机（求解）
        │   ├── C_main、C_ultrawide、C_tele、C_front   相机，MuJoCo 约定
        │   ├── C_cv、C_ultrawide_cv、C_tele_cv、C_front_cv   同样的相机，OpenCV 约定
        │   ├── B_back、S_lidar、L_flash   背面玻璃、激光雷达、闪光灯
        │   └── S_mount  支撑板上的 MagSafe 中心
        └── J_foot、J_bend   底座和手机支架之间支撑结构上的点
```

| 坐标系 | 定义 |
| --- | --- |
| `F_robot` | 原点在法兰面上，+Z 指向法兰外。对 reBot Arm B601-RS 来说，它就是 Seeed URDF 里的 `link6`（第 6 关节的转子端面）。 |
| `F_mount` | 在 `F_robot` 上方 `adapter_h` 处（沿 Z），再绕 Z 转 `mount_rot`。+X 指向杆倾斜的那一侧。不用转接件时 `adapter_h` 为 0。 |
| `T_tcp` | 半球形末端的顶点。+Z 是杆的方向。 |
| `P_phone` | 屏幕面的中心。+Y 指向手机有相机的那一端，+Z 指向屏幕外。 |
| `C_main` | 主摄，MuJoCo 约定：看向 −Z，+X 是画面右方，+Y 是画面上方。手机是横屏。 |
| `C_cv` | 同一个相机，OpenCV 约定：+Z 向前，+Y 是画面下方。 |

推杆底座上的螺钉孔是在 `F_robot` 里切的。改 `mount_rot` 时，孔始终对着法兰或转接件的孔位，转的是孔上面的推杆。

具体数值用 `asfinger frames <配置>` 或 `Model.root_to('T_tcp')` 得到。默认配置里，`T_tcp` 在 `F_robot` 里的位置是 (−100.09, 0, 178.70) mm。

### 手机坐标系的已知局限

- **`C_front` 是估计值。** Apple 只给了灵动岛区域的尺寸，没有给前置镜头的位置。这个坐标系放在该区域右侧圆头的中心。要用它，先在自己的手机上量一下。
- **`S_lidar` 和 `L_flash`**：它们高出背面玻璃多少，图纸上没有标，这里假定和镜头玻璃一样高。
- **`back_to_mount` 跟手机壳有关。** 它是手机背面到支撑板的距离，也就是手机壳背面的厚度。3.25 mm 是在一个 iPhone 17 Pro 手机壳上量出来的。请量自己的手机壳并修改这个参数。数值不对，所有相机坐标系都会沿手机法线方向偏移。
- 镜头位置取自 Apple 提供给配件厂商的尺寸图。相机坐标系在镜头的外表面上，不在镜头的光学中心。
