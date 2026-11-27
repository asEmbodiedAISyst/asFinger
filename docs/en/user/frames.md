# Frames

Frames are the interface of the tool. The robot flange, the TCP, the phone and each camera are named frames in one tree. Every output gives their poses, so the robot program, the simulation and the printed part agree.

## Conventions

- A frame has a parent, a position and a rotation. The root frame has `"parent": null`.
- A pose maps child coordinates to parent coordinates: `x_parent = R · x_child + p`.
- Positions are in millimetres. Quaternions are `[w, x, y, z]`, the order that MuJoCo uses.
- All outputs give a pose as a position and a quaternion.

## A frame entry

```json
"R_rod": {"parent": "F_tool", "pos": ["rod_x", 0, 0], "rot": {"axis": [0, 1, 0], "deg": "rod_tilt"},
          "module": "rod", "desc": "Rod axis at the adapter face; +Z along the rod toward the tip."}
```

`module` puts the frame in a group that an option can switch off. `desc` is free text.

### Rotation forms

| Form | Meaning |
| --- | --- |
| `{"axis": [x, y, z], "deg": a}` | A turn by `a` degrees about an axis. Use it when the angle is a parameter. |
| `{"quat": [w, x, y, z]}` | A quaternion. |
| `{"xyaxes": [x0, x1, x2, y0, y1, y2]}` | The X and Y axes of the child, given in the parent frame. |
| `{"mat": [9 numbers]}` | A rotation matrix, row by row. Its columns are the child axes in the parent frame. |
| a list of these forms | The rotations are applied in order, each one in the frame that the previous one gives. |

### A position from another frame

A frame can take its origin from a point in another frame. The point can slide along a direction until it reaches a plane.

```json
"J_foot": {"parent": "F_tool",
           "pos_from": {"frame": "S_mount", "pos": [0, 0, "-plate_t/2"], "dir": [-1, 0, 0],
                        "until": {"frame": "F_tool", "axis": "x", "value": "beam_x"}}}
```

This frame starts at a point below `S_mount` and moves along −X of `S_mount` until the X coordinate in `F_tool` equals `beam_x`. `"use": "xy"` takes only those coordinates from the point and the others from `pos`.

### An orientation from directions

`z_from` sets the Z axis to the sum of directions that are given in other frames. Two directions give their bisector. `x_hint` sets the X axis as near as possible to a direction.

```json
"J_bend": {"parent": "F_tool", "pos_from": {"frame": "J_foot"},
           "z_from": [{"frame": "F_tool", "dir": [0, 0, 1]}, {"frame": "S_mount", "dir": [1, 0, 0]}],
           "x_hint": {"frame": "F_tool", "dir": [0, 1, 0]}}
```

## Solved frames

A solved frame has a design intent (`solve`) instead of a fixed pose. A solver computes the pose. The config stores it as `result`.

```json
"P_phone": {"parent": "F_tool",
            "solve": {"type": "coplanar_look_at", "target": "T_tcp", "axis_frame": "R_rod", "camera": "C_main",
                      "plane_angle_deg": "phone_flange_angle", "v_n": "v_n", "distance_mm": "distance",
                      "image_up": "away_from_flange"},
            "result": {"pos": [...], "quat": [...], "solve_hash": "18a43136b678"}}
```

There is one solver, `coplanar_look_at`. It puts the phone so that:

- the optical axis of `camera` lies in the plane of the flange axis and the rod axis;
- the optical axis makes the angle `plane_angle_deg` with the flange axis;
- `target` appears at the horizontal centre of the image, at the height `v_n` (−1 is the bottom edge, 0 the centre, +1 the top edge);
- the lens is `distance_mm` from `target`;
- the top of the image points to the flange or away from it (`image_up`: `toward_flange` or `away_from_flange`).

`camera` must be a direct child frame of the solved frame.

A build always uses the stored `result`. The generator compares a hash of the solver inputs with the stored hash. If they differ, the result is stale, and the generator prints a warning. It does not replace the result.

> **Stale results give wrong geometry.** With a stale result, the phone, its holder and the checks use the old pose, but the rod uses the new parameters. Use `--resolve` after each change of a parameter that the solver uses: the rod, the tip, the camera position and the three parameters `phone_flange_angle`, `v_n` and `distance`.

`--resolve` runs the solvers again. Without `--set` and `--option`, it also writes the new results into the config file. The web editor always solves again.

## Frames of the default tool

The default config `iphone17pro_default.json` has this tree:

```text
F_robot                 the robot flange, as the robot defines it (root)
├── F_adapter           the mount adapter (same pose as F_robot)
└── F_mount             the face that the pusher base sits on
    └── F_tool          the tool side of the base plate
        ├── R_rod       the rod axis, +Z to the tip
        │   └── T_tip   the centre of the rod end face
        │       └── T_tcp   the apex of the tip: the contact reference point
        ├── P_phone     the phone (solved)
        │   ├── C_main, C_ultrawide, C_tele, C_front   cameras, MuJoCo convention
        │   ├── C_cv, C_ultrawide_cv, C_tele_cv, C_front_cv   the same cameras, OpenCV convention
        │   ├── B_back, S_lidar, L_flash   back glass, LiDAR scanner, flash
        │   └── S_mount  the MagSafe centre on the support plate
        └── J_foot, J_bend   points of the support between the base and the holder
```

| Frame | Definition |
| --- | --- |
| `F_robot` | Origin on the flange face, +Z out of the flange. For the reBot Arm B601-RS it is the `link6` frame of the Seeed URDF (the joint-6 rotor face). |
| `F_mount` | `adapter_h` above `F_robot` along Z, turned by `mount_rot` about Z. +X points to the side that the rod leans to. Without an adapter, `adapter_h` is 0. |
| `T_tcp` | The apex of the hemisphere tip. +Z is the rod direction. |
| `P_phone` | The `device` frame of [iMuninn](https://imuninn.projects.weijinqi.com/en/parameter-definition/): the centre of the display area, on the outer face of the front glass. +X points to the right edge, +Y to the top (the camera end), +Z out of the screen. |
| `C_main` | The main camera in the MuJoCo convention: it looks along −Z, +X is image right, +Y is image up. The phone is in landscape. |
| `C_cv` | The same camera in the OpenCV convention: +Z forward, +Y image down. |

The screw holes of the pusher base are cut in `F_robot`. When you change `mount_rot`, the holes stay on the pattern of the flange or the adapter, and the pusher turns above them.

Use `asfinger frames <config>` or `Model.root_to('T_tcp')` to get the numbers. In the default config, `T_tcp` is at (−100.09, 0, 178.70) mm in `F_robot`.

### Known limits of the phone frames

- **`C_front` is an estimate.** Apple gives dimensions only for the Dynamic Island area, not for the front lens. The frame is at the centre of the right round end of that area. Its axes follow iMuninn; the image rotation was measured on an iPhone 17 Pro, the axes were not checked against a target. Measure your phone before you use this frame.
- **The holder sits on the MagSafe circle.** The phone locks onto the holder by MagSafe, so `S_mount` is under the MagSafe centre (`magsafe_x`, `magsafe_y`), not under `P_phone`. On the iPhone 17 Pro the MagSafe centre is 2.735 mm below the display centre.
- **`S_lidar` and `L_flash`**: the height above the back glass is assumed equal to the lens glass. The drawings do not give it.
- **`back_to_mount` depends on the phone case.** It is the distance from the back of the phone to the support plate, which is the back thickness of the case. The value 3.25 mm is measured on one iPhone 17 Pro case. Measure your case and change the parameter. A wrong value moves all camera frames along the phone normal.
- The phone dimensions and the lens positions come from Apple's dimensional drawings for accessory makers, as read into iMuninn's phone data. `bump_h` is the height of the camera glass above the back: the camera plateau plus the lens glass (4.43 mm on the iPhone 17 Pro, checked on a real phone). The camera frames lie on the outer face of the lens, not at the optical centre of the lens.
- The phone's shape is the one iMuninn's glb draws: the body outline with rounded corners and one cylinder per rear lens window, up to the camera glass. The corner radius (`corner_r`, 0.15 × the short side) is an estimate, because Apple's drawings do not dimension it. The camera plateau, the LiDAR window, the buttons and the MagSafe ring are not drawn.
