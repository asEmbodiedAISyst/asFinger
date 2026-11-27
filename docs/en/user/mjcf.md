# MuJoCo export

`asfinger build` writes `ipush_tool.xml`, a MuJoCo model of the tool, and the meshes that it loads from `meshes/`. This page describes the content of the file and how to attach it to a robot.

## Content

The file has one body named `ipush`. All geometry is in metres. The body contains:

| Element | Source |
| --- | --- |
| Collision shapes | Boxes, spheres and cylinders from the shape trees. Class `ipush_col`, group 3, zero density. |
| Visual meshes | One mesh for each part, the full result of its shape tree. Class `ipush_vis`, group 1, no contact. |
| `<inertial>` | The mass, the centre of mass and the inertia of all parts together. They are computed from the meshes and the part densities. |
| Sites | One for each frame, with the frame name. |
| Cameras | One for each entry in `cameras`, at its frame, with `fovy` and `resolution`. |

A camera frame in the config already uses the MuJoCo convention (the camera looks along −Z), so no extra rotation is needed.

## The body frame

By default the body frame is the root frame of the config. A config can select a different frame and leave parts out:

```json
"mjcf": {"frame": "F_mount"},
...
{"name": "adapter_a", "mjcf": false, ...}
```

Use both when the robot model already contains the mount adapter. The default config does this. The URDF of the reBot Arm B601-RS includes the gripper connector as `link6`, so the default config writes the pusher alone, relative to the mounting face `F_mount`. `report.json` names the body frame and the parts that are included (`total.frame`, `total.parts`).

## Attach the tool to a robot

Attach the body `ipush` at the pose of the body frame on the robot. With the default config, that pose is `F_mount`: `adapter_h` above the flange face along the flange axis, turned by `mount_rot` about that axis.

With `mujoco.MjSpec`:

```python
import mujoco

robot = mujoco.MjSpec.from_file('robot.xml')
tool = mujoco.MjSpec.from_file('out/iphone17pro_default/ipush_tool.xml')
mount = robot.body('link6').add_frame(pos=[0, 0, 0.009], quat=[0, 0, 0, 1])  # F_mount of the default config
mount.attach_body(tool.body('ipush'), 'tool_', '')
model = robot.compile()
```

The numbers of this example are for the default config: `adapter_h` is 9 mm and `mount_rot` is 180°. Get the pose for another config from `Model.root_to('F_mount')`. The MJCF file loads its meshes from `meshes/` beside it, so keep the folder together.

After the attachment, the site `tool_T_tcp` is the TCP, and the camera `tool_C_main` is the main camera of the phone.

## Limits

- **Collision shapes are an approximation.** MuJoCo has no solid subtraction. For each difference, the generator keeps the base shape and drops the cuts, so holes and cut corners are filled in the collision model.
- **Imported meshes do not collide.** A mesh leaf gives no collision shape. A part can supply its own with `collision`. In the default config, the phone holder collides as one box.
- **The mass is an estimate.** It is the solid volume multiplied by the density of each part. A printed part with less than 100 % infill is lighter. The phone is a box with a density that gives 206 g.
- **Camera intrinsics are simple.** A camera has only a vertical field of view and a resolution. Lens distortion is not modelled.
- The body, the classes and the file are named `ipush`. These names come from an earlier name of the project and are kept for compatibility.
