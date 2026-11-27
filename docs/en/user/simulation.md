# Simulation

`sim/` holds the test scene of the setup in MuJoCo: the arm in its box, the whiteboard with its markers, a cube and both cameras. The scene runs under the same control library as the real arm, so the same control code runs on both. The tools in `robot/` use it when you add `--sim`.

This is a first scene. Positions agree with the real setup to about 1 cm. Contact and appearance are rough. A second scene with the real meshes of the arm, the closed box and tuned lights is described in [The twin scene](simulation-twin.md).

## Use it

```bash
uv run python sim/scene.py render --out /tmp/asfinger-sim     # both camera views at the registration pose
uv run python sim/scene.py push                               # push the cube 10 cm and report where it ends
uv run python sim/scene.py view                               # interactive viewer (needs a display)
uv run python robot/arm_move.py --waypoints "0,15,20,=,0,0" --sim   # a tool of robot/ in the scene
```

From code:

```python
import sys

sys.path.insert(0, 'sim')
from scene import make_arm, render, object_pose

with make_arm() as arm:  # a rebot_control.Arm on the simulator, with the scene
    arm.enable()
    arm.move_home()
    image = render(arm, 'top')  # the RGB picture that the top phone would see; "wrist" is the other camera
    position, rotation = object_pose(arm, 'cube')
```

### The GL backend

Rendering needs an OpenGL context. `scene.py` sets `MUJOCO_GL=egl` when the variable is not set, which renders without a display on Linux with a GPU. Set the variable yourself in other cases:

| Value | Use |
| --- | --- |
| `egl` | Linux, off-screen. The default of `scene.py`. |
| `glfw` | macOS, and Linux with a display. |
| `disable` | No rendering. Enough for the tools with `--sim` and for `scene.py push`; the tests in CI use it. |

## The files

| File | Content |
| --- | --- |
| `sim/scene.yaml` | The values that are measured by hand or estimated: the box, the whiteboard, the cube, the collision shape of the pusher, the camera intrinsics. Each number says how it was obtained. |
| `sim/registration.yaml` | Where the cameras, the whiteboard and the markers are in the arm frame. `sim/register.py` writes this file as a whole. Do not edit it. |
| `sim/register.py` | Computes that file from two pictures of the real scene. |
| `sim/scene.py` | Builds the scene, renders, and holds the examples above. |
| `sim/assets/` | The marker textures and the mesh of the printed pusher, `ipush_print.stl`. |

All positions are in the arm frame. See [The robot setup](robot-setup.md#the-arm-frame).

## How the positions were obtained

`sim/register.py` makes a rough registration from one pose. It is good to about 1 cm and is not a camera calibration.

1. The tilt of the top camera comes from the gravity reading of the phone, and its height from the markers on the whiteboard. With these, a pixel becomes a point on the plane of the whiteboard.
2. The arm stands still at a known pose. Forward kinematics gives the tip and the direction of the rod. The tip and the line of the rod are picked in the top picture. This ties the arm frame to the camera.
3. The whiteboard and the markers are placed from their corners in the top picture.
4. The wrist camera is placed with PnP on the markers that it sees. Then it is moved sideways until the rod tip appears where the wrist picture shows it.

`register.py` reads two pictures of the real scene, named in `sim/scene.yaml`. These pictures are not in the repository. To register your own scene, take them with `robot/snapshot.py` while the arm stands at `registration.q_deg`, save them under the names in `sim/scene.yaml`, and run:

```bash
uv run python sim/register.py            # compute and print
uv run python sim/register.py --write    # also write sim/registration.yaml
```

Run it again after the whiteboard, the cube or a camera moved. `scene.py render --compare` compares the marker corners of the rendered pictures with the real ones when the pictures are there.

## What is not modelled, or only estimated

- **The links of the arm do not collide.** They are drawn as capsules between the joints. Only the pusher touches things. Do not use the simulator to decide if the real arm will hit something.
- **Contact and friction are MuJoCo defaults or estimates.** They are not identified from real pushes. A push in the simulator shows a tendency only.
- **Estimated sizes:** the outline and thickness of the whiteboard, the edge and mass of the cube, the start of the visible rod. Measure them and change `sim/scene.yaml`.
- **Cameras:** the real intrinsics, but no lens distortion, no exposure and no colour model. The walls, the lights, the colour card and the cables have no appearance.
- **Motors:** an ideal PD loop with feedforward. Friction and the torque ripple of the real motors are in the simulator only when a tool is started with its `--sim-friction` or `--sim-ripple` option.
- **Agreement with the real pictures:** the corners of the markers in the rendered top picture are about 3 pixels from the real ones (1920 × 1440). In the wrist picture (640 × 480) the difference is 9 to 14 pixels, because the position of that camera is known to about 1 cm only.

## The model of the pusher

`sim/assets/meshes/ipush_print.stl` is the pusher that is on the arm, in millimetres. Its frame is `F_robot` of [the as-built frames](robot-calibration.md#the-frames-of-the-pusher-as-built). The file name comes from an earlier name of the project.

| Part | Size |
| --- | --- |
| Mounting disc | Diameter 56.8 mm, 10 mm thick, bottom face on z = 0. Four holes on a circle of radius 19 mm, at ±45° and ±135°. |
| Rod | Round, diameter 15 mm, at 30° to the axis of the disc. |
| Tip | A hemisphere. Centre at (96.3, 0, 163.2) mm, farthest point at (100.1, 0, 169.7) mm. |
| Phone plate | On the other side of the rod. Its normal is at 55° to the axis of the disc. |

In this scene the pusher is one capsule with a radius of 7.5 mm that ends in the tip sphere of the real rod. The STL is not drawn.
