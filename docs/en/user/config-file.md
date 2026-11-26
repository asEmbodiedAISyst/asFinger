# The config file

A config is one JSON file that describes one tool: its parameters, its frames and its solid parts. This page describes each section of the file and ends with a complete example.

## Sections

| Key | Content |
| --- | --- |
| `name` | The name of the tool. It becomes the model name in the MJCF file. |
| `description` | Free text. |
| `root` | The name of the root frame. All outputs use this frame unless a section says otherwise. |
| `params` | Named numbers and expressions. |
| `param_notes` | Optional notes for parameters. The generator does not read them. |
| `frames` | The frame tree. See [Frames](frames.md). |
| `parts` | The solids. Each part is bound to a frame. |
| `shapes` | Named shapes that several parts can use. |
| `options` | Switches for groups of frames and parts. |
| `print_sets` | Printed parts that are fused into one STL file. |
| `cameras` | The cameras of the tool. |
| `checks`, `interference` | Limits and overlap rules. See [Checks and interference rules](checks.md). |
| `references` | Meshes that only the preview shows, for comparison with a real part. |
| `mjcf` | Settings for the MuJoCo export. See [MuJoCo export](mjcf.md). |

Lengths are in millimetres. Angles are in degrees. Densities are in g/cm³.

## Parameters and expressions

A parameter is a number or an expression in a string. An expression can use other parameters.

```json
"params": {
  "rod_D": 15,
  "rod_tilt": 30,
  "tip_R": "rod_D/2",
  "rod_embed": "rod_D/2*tand(rod_tilt) + 1"
}
```

Most numbers in the other sections can also be expressions, for example `"pos": [0, 0, "base_t/2"]`.

An expression can contain:

- numbers and parameter names;
- the operators `+ - * / // % **` and parentheses;
- comparisons (`<`, `<=`, `>`, `>=`, `==`, `!=`), which give 1 or 0;
- a choice: `a if condition else b`;
- the constants `pi`, `true` and `false`;
- the functions `sin cos tan asin acos atan atan2` (radians), `sind cosd tand asind acosd atand atan2d` (degrees), `sqrt abs min max round radians degrees`.

Other Python syntax is an error. The web editor evaluates a config with the same Python code, so the results are equal.

## Parts

A part is one solid. It has a name, a frame and a shape tree (`csg`).

```json
{
  "name": "tool_body", "frame": "F_mount", "role": "printed", "density": 1.24, "color": "#8a94a6",
  "csg": {"union": [ ... ]}
}
```

| Key | Meaning |
| --- | --- |
| `name` | The file name of the part in `print/` and `meshes/`. |
| `frame` | The frame that the shape tree starts in. A printed part is written to STL in this frame. |
| `role` | `"printed"` writes the part to `print/`. The default configs also use `"reference"` (the phone) and `"hardware"` (bought parts). |
| `density` | In g/cm³, for mass and inertia. The default is 1.0. |
| `color` | A hex colour for the preview, the editor and the MJCF file. |
| `enabled` | An expression. The part is left out when it is 0. |
| `mjcf` | `false` leaves the part out of the MJCF file. |
| `collision` | A list of shapes that replace the automatic collision shapes in the MJCF file. |

## Shapes

A shape tree is made of four leaf shapes and two operations.

| Shape | Form |
| --- | --- |
| Box | `{"box": {"size": [x, y, z]}}`, centred on its origin |
| Bar between two points | `{"box": {"size": [w, t], "from": PT, "to": PT, "up": [x, y, z]}}` |
| Box between two corners | `{"box": {"corners": [PT, PT]}}`, with its edges along the axes of the node |
| Sphere | `{"sphere": {"r": r}}` |
| Cylinder | `{"cylinder": {"r": r, "h": h}}`, along the local Z axis, centred on its origin |
| Cylinder between two points | `{"cylinder": {"r": r, "from": PT, "to": PT}}` |
| Imported mesh | `{"mesh": {"file": "assets/x.stl", "scale": 1}}` |
| Union | `{"union": [node, node, ...]}` |
| Difference | `{"difference": [base, cut, cut, ...]}` |

`PT` is a point. Write it as `[x, y, z]` in the frame of the node, or as `{"frame": "S_mount", "pos": [x, y, z]}` in a named frame. A point in a named frame lets one shape connect two frames. The shape then follows both frames when a parameter changes.

A bar or a cylinder between two points can be made longer with `extend_from` and `extend_to` (bars) or `extend` (millimetres).

Each node can also have these keys:

| Key | Meaning |
| --- | --- |
| `name` | A name for the node. Interference rules and tests refer to it. |
| `pos`, `rot` | The pose of the node in the frame of its parent node. `rot` uses the forms in [Frames](frames.md#rotation-forms). |
| `frame` | Put this node in a named frame instead of the frame of its parent node. |
| `enabled` | An expression. The node is left out when it is 0. |
| `sim` | For a leaf: `"collide"` (default) makes it a MuJoCo collision shape, `"none"` does not. |
| `color` | A colour for this node. |

An imported mesh must be a closed solid. The path in `file` is relative to the parent of the folder that holds the config. In this repository, a config in `hardware/configs/` loads `assets/x.stl` from `hardware/assets/x.stl`. An absolute path also works.

### Shared shapes

Put a shape tree under `shapes` to use it in more than one place:

```json
"shapes": {"connector_b": {"difference": [ ... ]}},
...
{"use": "connector_b", "frame": "F_adapter"}
```

A `use` node can have its own `name`, `pos`, `rot`, `frame` and `enabled`.

## Options

An option switches a group of frames off, together with all that depends on them.

```json
"options": {
  "phone": {"value": true, "modules": ["phone", "holder", "connector"],
            "desc": "Phone camera with its holder. Off = the rod alone."}
}
```

Each frame can name a `module`. When an option is off, the generator drops:

- the frames of its modules, and each frame that depends on a dropped frame;
- the shapes that refer to a dropped frame;
- parts that become empty, and the cameras, checks, references and print-set members on dropped frames.

The solver of a dropped frame does not run. The config file keeps all its content. Switch an option with `--option phone=0` or `m.set_options(phone=False)`.

## Print sets

A print set fuses several printed parts into one STL file:

```json
"print_sets": {"ipush_print": ["tool_body", "holder"]}
```

The file is `print/ipush_print.stl`. It is written in the frame of the first part in the list. `report.json` gives the number of bodies of each print set. A print set that must print as one piece has 1 body. If the number is larger, the parts do not touch.

## Cameras

A camera has the name of a frame. That frame gives its pose.

```json
"cameras": {
  "C_main": {"fovy_deg": "2*atand(sqrt(36**2 + 24**2)*0.6/2/feq)", "aspect": "4/3",
             "resolution": [640, 480], "min_focus_mm": null}
}
```

`fovy_deg` is the vertical field of view. `aspect` is width / height (default 4/3). `resolution` is written to the MJCF file. If `min_focus_mm` is a number, the solver warns when the camera is nearer to its target than this distance.

The camera data of the default config has these limits:

- `min_focus_mm` is `null` for all cameras, because Apple does not publish it. The focus check is off.
- The field of view of `C_main` and `C_tele` comes from the equivalent focal length. It is not measured. The value of `C_ultrawide` is measured with the focus at infinity.
- The pose of the front camera `C_front` is an estimate. See [Frames](frames.md#frames-of-the-default-tool).

## A complete example

This config is a base disc, a tilted rod and a ball tip. Save it as `my_tool/configs/minimal_rod.json`.

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

Build it:

```bash
asfinger build my_tool/configs/minimal_rod.json -o out/minimal_rod
```

The build writes `print/rod.stl`, `meshes/rod.stl`, `ipush_tool.xml`, `preview.html`, `resolved.json` and `report.json`. The report gives a mass of 46.8 g. This config has no camera `C_main`, so `preview.html` stays empty (see [Quick start](quickstart.md#the-output-files)).

Now tilt the rod until the check fails:

```bash
asfinger frames my_tool/configs/minimal_rod.json --set rod_tilt=70
```

```text
T_tcp     pos=[119.81, 0.0, 51.61]  z=[0.94, 0.0, 0.342]  module
[check] The tip is too close to the flange: make rod_L longer or rod_tilt smaller. (T_tcp.z = 51.61, allowed 60.0 .. )
```
