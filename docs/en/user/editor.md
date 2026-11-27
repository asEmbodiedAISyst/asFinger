# The web editor

The [asFinger editor](https://asembodiedaisyst.github.io/asFinger/editor/) builds a pusher in the browser. You select the components, change the parameters, examine the result in 3D, and export the config and the STL files. No installation and no account are necessary.

The editor needs a desktop browser with a window at least 1100 px wide.

## What runs in the browser

The editor has no server side. The page downloads the Python runtime Pyodide and the `asfinger` package, and runs them in a web worker. The solid modelling uses the WebAssembly build of Manifold. The Python code is the same code that the command line uses.

- The first load takes a few seconds, because the page downloads about 13 MB.
- After that, each change is solved in about 0.1 to 0.3 seconds.
- Your selection and your parameters are stored in this browser only (local storage). Nothing is uploaded.

## The three areas

The 3D view fills the window. Two panels float over it.

| Area | Where | Function |
| --- | --- | --- |
| **Config** | Left | A rail with one button for each group. A click opens the cards of that group. |
| **View** | Centre | The 3D view, with a selection bar in the top strip. |
| **Inspect** | Right | Information about the selected component, and below it the parameters and the export buttons. Open it with the tab "Parameters & info". |

The top strip also has the switch for light and dark appearance, the language switch and the link to these pages.

## Config: select the components

The tool is made of five groups.

| Group | Selection | Effect |
| --- | --- | --- |
| Carrier | reBot Arm RS, Franka FR3, UR5e, human hand, or a custom flange | Sets the flange hole pattern and the default mounting angle. |
| Flange adapter | None, Connector A + B, Fused connector | Sets the hole pattern, the height and the screw direction of the pusher base. |
| Pusher | Round rod v1 | The rod and the phone holder. |
| Tip | Bare tip | The hemisphere at the end of the rod. The TCP is its apex. |
| Camera | iPhone 18 Pro, iPhone 17 Pro, iPhone 17, iPhone 16 Pro, iPhone 15 Pro, iPhone 14 Pro | Sets the phone dimensions and the lens positions. |

Items marked "Planned" are not available yet.

The groups depend on each other:

- When you select a carrier, the editor also selects the default adapter of that carrier.
- An adapter decides the hole pattern of the pusher base. With the adapter "None", the carrier decides it.
- The carrier gives the default mounting angle, so that the phone is on top on every arm.
- With the carrier "Custom flange", you enter the hole pattern in the pusher parameters. The base has four holes on one circle, as two opposite pairs.
- A phone fixes the phone size, the camera positions and the height of the camera glass, and switches the telephoto and LiDAR frames off when the phone has none. The editor then solves the phone pose again so that the main camera still looks at the TCP, and the holder moves with the phone. The holder sits on the phone's MagSafe circle. All phones take their values from Apple's dimensional drawings, as read into the phone data of [iMuninn](https://imuninn.projects.weijinqi.com/en/parameter-definition/); the iPhone 17 Pro values are those of the config.

Parameters that another group decides are read-only. They appear in the section "Set by other groups".

## View: examine the model

- Select a group or a card. The camera moves to that component and outlines it. Inspect then shows its data.
- A chip in the selection bar shows one component alone. Click the chip again, or "Full assembly", to go back.
- "Reset view" returns to the start view.
- The frames are drawn with X red, Y green and Z blue.
- A solid shown in red is an overlap that an interference rule found.

## Inspect: parameters and checks

The parameter list starts with the values that most people change, for example the rod length, the rod tilt, the mounting angle and the three values that aim the camera. Tick "Advanced" to see the others. "Reset" restores the values of the config.

The editor solves the model again after each change, so the phone pose is always up to date. It then runs the checks and the interference rules of the config (see [Checks and interference rules](checks.md)). A failed test appears as a message, and the overlap is shown in red.

## Export

| Button | File | Use |
| --- | --- | --- |
| Print STL | `ipush_print_<carrier>_<adapter>.stl` (`_<phone>` is added for a phone other than the iPhone 17 Pro) | The pusher and the phone holder fused into one body. The mounting face is on z = 0. Slice it with this face on the bed. |
| Config JSON | `ipush_<carrier>_<adapter>.json` | The config with your parameters and the solved frames. Build it later with `asfinger build`. |
| Part STL | `tool_body_<carrier>_<adapter>.stl`, `holder_<carrier>_<adapter>.stl` | One part alone, in its own frame. |

While a check or an interference rule with the level "error" fails, only the config can be exported. A warning does not block the export.

An STL file from the editor and the STL file that `asfinger build` writes for the same config describe the same solid. The files are not identical byte for byte, because the browser and the Python package use different builds of Manifold, which divide the surfaces into triangles differently.

To build the exported config on your computer, put it in a folder `configs/` that has the folder `assets/` of this repository beside it. `hardware/configs/` is such a place. The config loads the phone holder mesh from `assets/`.

## Limits

- **Printed and tested: one combination.** Only the round rod for the iPhone 17 Pro on the reBot Arm RS is printed and used on a real arm. The "Fused connector" adapter is not printed yet.
- **Values to verify.** Some data in the information panel is marked "to verify". It does not come from an official drawing, or a program read it from the drawing and nobody has checked it yet. Examine it before you depend on it.
- **Other phones are not printed.** The holder and the case gap (`back_to_mount`) were made for an iPhone 17 Pro in its case. For another phone, check the case thickness before you print.
- **The printed pusher is older than the phone data.** The pusher printed on 2026-11-08 was solved with a camera glass height of 1.88 mm and the holder under the display centre. With the phone data of 2026-11-27, the default config moves the holder by 3.7 mm so that the camera looks at the TCP as intended.
- **The human hand carrier is a placeholder.** The grip model in the view is a sketch, and its dimensions are not final.
- **Four screw holes only.** The pusher base supports four holes as two opposite pairs. A flange with six holes is not supported.
- **The arm models are for display.** The arm in the view shows how the tool sits on the flange. The editor does not test collisions with the arm.
- **Supports and material.** The phone plate and the snaps need print supports. The snaps are brittle in matte PLA. Print them in PETG, or flat as a separate part.
- The limits of the tests and of the phone frames also apply here. See [Checks and interference rules](checks.md#what-the-tests-do-not-find) and [Frames](frames.md#known-limits-of-the-phone-frames).
