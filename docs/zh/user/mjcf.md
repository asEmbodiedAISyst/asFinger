# 导出到 MuJoCo

`asfinger build` 会写出 `ipush_tool.xml`，这是工具的 MuJoCo 模型；它用到的网格在 `meshes/` 里。这一页说明文件的内容，以及怎样把它装到机械臂上。

## 内容

文件里只有一个 body，名字是 `ipush`。几何数据的单位都是米。body 里有：

| 元素 | 来源 |
| --- | --- |
| 碰撞体 | 形状树里的长方体、球和圆柱。class 为 `ipush_col`，group 3，密度为 0。 |
| 视觉网格 | 每个零件一个网格，是它的形状树算出来的完整结果。class 为 `ipush_vis`，group 1，不参与接触。 |
| `<inertial>` | 所有零件合在一起的质量、质心和惯量，由网格和各零件的密度算出。 |
| site | 每个坐标系一个，名字和坐标系相同。 |
| 相机 | `cameras` 里每一项对应一个，位于同名坐标系上，带 `fovy` 和 `resolution`。 |

配置里的相机坐标系本来就是 MuJoCo 约定（相机看向 −Z），不用再转。

## body 的坐标系

默认情况下，body 的坐标系就是配置的根坐标系。配置可以另选一个坐标系，也可以让某些零件不进 MJCF：

```json
"mjcf": {"frame": "F_mount"},
...
{"name": "adapter_a", "mjcf": false, ...}
```

机械臂模型里已经带有法兰转接件时，两处一起用。默认配置就是这样做的：reBot Arm B601-RS 的 URDF 把夹爪连接件算作 `link6`，所以默认配置只输出推杆本身，坐标相对于安装面 `F_mount`。`report.json` 里记着 body 的坐标系和包含的零件（`total.frame`、`total.parts`）。

## 把工具装到机械臂上

把 body `ipush` 挂到机械臂上“body 坐标系”所在的位姿。用默认配置时，这个位姿就是 `F_mount`：从法兰面沿法兰轴线抬高 `adapter_h`，再绕轴线转 `mount_rot`。

用 `mujoco.MjSpec` 的写法：

```python
import mujoco

robot = mujoco.MjSpec.from_file('robot.xml')
tool = mujoco.MjSpec.from_file('out/iphone17pro_default/ipush_tool.xml')
mount = robot.body('link6').add_frame(pos=[0, 0, 0.009], quat=[0, 0, 0, 1])  # F_mount of the default config
mount.attach_body(tool.body('ipush'), 'tool_', '')
model = robot.compile()
```

例子里的数值对应默认配置：`adapter_h` 是 9 mm，`mount_rot` 是 180°。别的配置用 `Model.root_to('F_mount')` 取位姿。MJCF 文件从旁边的 `meshes/` 目录读网格，两者要放在一起。

挂好之后，site `tool_T_tcp` 就是 TCP，相机 `tool_C_main` 就是手机的主摄。

## 局限

- **碰撞体是近似的。** MuJoCo 不能做实体相减。遇到差集，生成器只保留被减体，减掉的部分直接丢弃，所以碰撞模型里的孔和切角都是实心的。
- **导入的网格不参与碰撞。** mesh 节点不会生成碰撞体，零件可以用 `collision` 自己指定。默认配置里，手机支架的碰撞体是一个长方体。
- **质量是估计值。** 它等于实体体积乘以各零件的密度。打印件填充率不到 100 % 时会更轻。手机是一个长方体，密度按总重 206 g 设定。
- **相机内参很简单。** 相机只有竖直视场角和分辨率，没有镜头畸变。
- body、class 和文件名里的 `ipush` 来自项目以前的名字，为了兼容没有改。
