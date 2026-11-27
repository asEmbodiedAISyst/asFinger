# 仿真

`sim/` 里是这套设备的测试场景的 MuJoCo 版本：箱子里的机械臂、带标记的白板、一个方块，以及两台相机。场景和真机用同一套控制库，所以同一段控制代码两边都能跑。`robot/` 里的工具加 `--sim` 时用的就是它。

这是第一版场景：位置和真实设备对得上，约 1 cm 以内；接触和外观都比较粗。第二个场景用了机械臂的真实网格、封闭的箱子和调过的灯光，见[孪生场景](simulation-twin.md)。

## 怎么用

```bash
uv run python sim/scene.py render --out /tmp/asfinger-sim     # 在配准姿态下渲染两台相机的画面
uv run python sim/scene.py push                               # 把方块推 10 cm，报告它最后在哪
uv run python sim/scene.py view                               # 交互式查看（需要显示器）
uv run python robot/arm_move.py --waypoints "0,15,20,=,0,0" --sim   # 在场景里运行 robot/ 的工具
```

在代码里：

```python
import sys

sys.path.insert(0, 'sim')
from scene import make_arm, render, object_pose

with make_arm() as arm:  # 仿真后端上的 rebot_control.Arm，带着场景
    arm.enable()
    arm.move_home()
    image = render(arm, 'top')  # 顶部手机会看到的 RGB 画面；"wrist" 是另一台相机
    position, rotation = object_pose(arm, 'cube')
```

### GL 后端

渲染需要一个 OpenGL 上下文。环境变量 `MUJOCO_GL` 没有设置时，`scene.py` 把它设成 `egl`，在带显卡的 Linux 上不需要显示器就能渲染。其他情况要自己设：

| 取值 | 用途 |
| --- | --- |
| `egl` | Linux，离屏渲染。`scene.py` 的默认值。 |
| `glfw` | macOS，以及有显示器的 Linux。 |
| `disable` | 不渲染。带 `--sim` 的工具和 `scene.py push` 用它就够了，CI 里的测试也用它。 |

## 文件

| 文件 | 内容 |
| --- | --- |
| `sim/scene.yaml` | 手工量的或暂估的数值：箱子、白板、方块、推杆的碰撞形状、相机内参。每个数都注明了来历。 |
| `sim/registration.yaml` | 相机、白板和标记在机械臂坐标系里的位置。由 `sim/register.py` 整体重写，不要手改。 |
| `sim/register.py` | 根据真实场景的两张照片算出上面那份文件。 |
| `sim/scene.py` | 搭场景、渲染，以及上面那些例子。 |
| `sim/assets/` | 标记贴图，和打印推杆的网格 `ipush_print.stl`。 |

所有位置都在机械臂坐标系里，见[真机环境](robot-setup.md#机械臂坐标系)。

## 位置是怎么得到的

`sim/register.py` 做的是一次单姿态的粗配准，精度约 1 cm，不是相机标定。

1. 顶部相机的倾角来自手机的重力读数，高度来自白板上的标记。有了这两样，画面里的像素就能换算成白板平面上的点。
2. 机械臂静止在已知姿态，正运动学给出杆尖的位置和推杆的方向；在顶部画面里点出杆尖和推杆的走向，机械臂坐标系就和相机对上了。
3. 白板和标记的位置由它们在顶部画面里的角点换算得到。
4. 腕部相机用它看到的标记做 PnP，再横向挪一点，让杆尖出现在腕部画面里实际的位置上。

`register.py` 要读真实场景的两张照片，文件名写在 `sim/scene.yaml` 里。这两张照片不在仓库里。要配准你自己的场景，就让机械臂停在 `registration.q_deg`，用 `robot/snapshot.py` 各拍一张，按 `sim/scene.yaml` 里的名字存好，然后运行：

```bash
uv run python sim/register.py            # 计算并打印
uv run python sim/register.py --write    # 同时写入 sim/registration.yaml
```

白板、方块或者相机挪动过以后要重新做一遍。照片在的时候，`scene.py render --compare` 会把渲染画面里的标记角点和真实照片里的做比较。

## 没有建模，或只是暂估的

- **机械臂的连杆不参与碰撞**，画出来只是关节之间的胶囊体，只有推杆会碰到东西。不要用仿真来判断真机会不会撞。
- **接触和摩擦是 MuJoCo 的默认值或暂估值**，没有对照真实的推动数据辨识过。仿真里推一下只能看个趋势。
- **暂估的尺寸：** 白板的外形和厚度、方块的边长和质量、推杆可见部分的起点。量过之后改 `sim/scene.yaml`。
- **相机：** 用的是真实内参，但没有镜头畸变，也没有曝光和颜色模型。箱壁、灯光、色卡、线缆都没有做外观。
- **电机：** 理想的 PD 加前馈。真实电机的摩擦和力矩波动，只有在工具带着 `--sim-friction` 或 `--sim-ripple` 启动时才出现在仿真里。
- **和真实画面的吻合程度：** 渲染出的顶部画面（1920 × 1440）里，标记角点和真实照片差约 3 像素；腕部画面（640 × 480）差 9 到 14 像素，因为这台相机的位置本身只准到 1 cm 左右。

## 推杆的模型

`sim/assets/meshes/ipush_print.stl` 是装在机械臂上的那根推杆，单位毫米。它的坐标系就是[推杆实物的坐标系](robot-calibration.md#推杆实物的坐标系)里的 `F_robot`。文件名来自项目以前的名字。

| 部分 | 尺寸 |
| --- | --- |
| 安装盘 | 直径 56.8 mm，厚 10 mm，底面在 z = 0。4 个孔在半径 19 mm 的圆上，方位 ±45° 和 ±135°。 |
| 推杆 | 圆杆，直径 15 mm，和安装盘轴线成 30°。 |
| 杆尖 | 半球。球心在 (96.3, 0, 163.2) mm，最远点在 (100.1, 0, 169.7) mm。 |
| 手机板 | 在推杆的另一侧，法线和安装盘轴线成 55°。 |

在这个场景里，推杆是一根半径 7.5 mm 的胶囊体，末端和真实推杆的杆尖球重合；STL 本身没有画出来。
