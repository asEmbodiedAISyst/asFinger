# The Fusion add-in

The add-in builds a config as a parametric design in Autodesk Fusion, and updates that design in place when you change a parameter. It is in `hardware/cad/fusion/` of the repository.

| Folder | Content |
| --- | --- |
| `asFingerAddIn/` | The add-in: a palette with the parameters, and a local HTTP server that receives configs. |
| `asFingerFromJSON/` | A script that builds one `resolved.json` in a new document. |
| `asfinger_fusion/` | The code that both use to make and to change the features. You do not install it. |

## Install

You need Autodesk Fusion on Windows or macOS, and a clone of this repository on the same computer. The add-in imports the package from `src/asfinger` of the clone with the Python of Fusion. You do not install a package into Fusion, and the add-in does not need numpy.

1. If the earlier iPush add-in is in the list of Fusion, stop it and clear its "Run on Startup" box. The two add-ins use the same port.
2. In Fusion, open Utilities > Add-Ins > Scripts and Add-Ins.
3. Click `+` and select the folder `hardware/cad/fusion/asFingerAddIn`.
4. Select asFingerAddIn in the list and run it. The add-in then starts each time Fusion starts.

Leave the folders where they are. The add-in finds the package, `asfinger_fusion/` and the default config by their position in the repository.

The add-in adds a button "asFinger" to the Add-Ins panel (Utilities) and to the Create panel (Solid). The button opens the palette.

## The palette

The palette opens at the right side of the window. Its text is English, or Chinese when the language of the system is Chinese. It shows the name and the path of a config and one field for each parameter. The first config is `hardware/configs/iphone17pro_default.json`.

- A parameter that is a number has a number field. A parameter that is an expression has a text field, and its value is shown below the field.
- A field that you changed has a blue border.
- The parameters are in groups by name. A parameter that fits no group is in "Other".

| Control | Function |
| --- | --- |
| Apply (update in place) | Sends your edits to Fusion. See the next section. |
| Rebuild | Deletes the generated design and builds it again in the same document. The palette asks you to confirm. |
| Undo edits | Puts every field back to the value of the last load or the last Apply. It does not change the design. |
| Change config… | Opens a file dialog and loads another config. The add-in stores the path in `settings.json` in its folder and loads that config the next time. |
| Write the parameters back into the config file on Apply | When ticked, Apply also saves the config file with your edits and the new solver results. |

After each operation, the bottom of the palette shows the result: the operation, the number of changes, the positions of `T_tcp`, `C_main` and `S_mount` in the root frame, and the messages of the build.

## Update in place, rebuild, new document

Apply does these steps:

1. It loads the config, applies your edits and runs the solvers again. The result is the same as with `--resolve` on the command line.
2. It runs the checks of the config. If a check fails, the design does not change and the palette shows the messages.
3. If the active document is not a design that the add-in made, it builds the model in a new document.
4. If the active document is such a design, it updates the design in place.

**Update in place** changes the values of the features that exist: sketch dimensions, extrude distances, the Move feature of each shape, the points of the frames, the mesh bodies and the user parameters. Features that you added by hand, for example fillets and chamfers, stay.

An update is possible only when the structure of the model is the same: the same parts, the same shapes with the same names, and the same frames. A parameter that changes only sizes and positions keeps the structure. If the structure changed, the palette shows "structure changed" and the design stays as it was. Use Rebuild then.

**Rebuild** removes all features of the document, also the features that you added, and all components and user parameters. Then it builds the model again in the same document.

The add-in finds its features through attributes, not through names. You can rename a feature. If you delete a generated feature, the next update lists it after "Not found".

## What the design contains

- Each part is a component with a timeline group.
- Each box, cylinder and sphere is a dimensioned sketch, an Extrude or a Revolve, and a Move feature that puts the body in place. Each union and difference is a Combine feature.
- Each frame is a Joint Origin with the name of the frame. The Joint Origins sit on the hidden sketch `asfinger_frames` in the root component.
- Each parameter that is a number is a user parameter. Names that end in `_angle`, `_tilt`, `_rot` or `_deg` are in degrees, `v_n` and `u_n` have no unit, and the others are in millimetres.
- A part that is one imported mesh, such as the phone holder of the default config, is a mesh body.

## Send a config from the command line

```bash
asfinger send hardware/configs/iphone17pro_default.json --set rod_L=150
```

The command sends the path of the config and the values of `--set` to the add-in. Fusion reads the file, so Fusion and the command must run on the same computer. The add-in then does the same steps as Apply.

| Flag | Function |
| --- | --- |
| `--set NAME=VALUE` | Change a parameter for this request. Use it more than once for more parameters. |
| `--rebuild` | Rebuild the design. Without this flag, the add-in updates in place. |
| `--save` | Let Fusion write the edits and the new solver results into the config file. |
| `--port N` | Send to another port. The add-in listens on 47910 only. |

The command prints `{"ok": true, "queued": true}`. This means that Fusion received the request. The result appears in the palette, if the palette is open. The command does not wait for the result and does not print it.

Another program can send the same request:

```text
POST http://127.0.0.1:47910/ipush/apply
{"config": "/absolute/path/config.json", "params": {"rod_L": "150"}, "mode": "update", "save": false}
```

`config` is a path, or the config itself as a JSON object. `mode` is `update`, `rebuild` or `new` (always a new document). The request must not have an `Origin` header. A browser adds that header to the requests of a web page, so a web page cannot send a config: the add-in answers 403. A GET request returns `{"ok": true, "app": "ipush-fusion", "port": 47910}`. The path `/ipush/apply` and the name `ipush-fusion` come from an earlier name of the project.

## Use a config from the web editor

The web editor does not send to Fusion. Export the config in the editor (button "Config JSON"), and put the file into `hardware/configs/` of your clone, or into another folder `configs/` that has the folder `assets/` beside it. Then load the file with "Change config…" in the palette, or send it with `asfinger send`.

## The script asFingerFromJSON

The script builds a design from a `resolved.json` that `asfinger build` wrote. It does not import the package.

1. Add the folder `hardware/cad/fusion/asFingerFromJSON` in Scripts and Add-Ins in the same way as the add-in.
2. Run the script and select a `resolved.json`.
3. The script builds the model in a new document and shows the number of parts and Joint Origins.

The script finds the meshes through the key `base_dir` of the file. If the key is absent, it expects the file in `out/<name>/` of the repository and looks for `assets/` in `hardware/`.

## Limits

- **Tried in Fusion by hand, not tested automatically.** From this repository the add-in was run in Fusion for these cases: a build in a new document, an update in place from `asfinger send`, and the refusal of a request from a web page. Rebuild, the script asFingerFromJSON and an update of a design that the earlier add-in made were not tried. The automatic tests run without Fusion: the paths, the list of parameters, the HTTP server and the agreement with `asfinger send`.
- **One port.** The port 47910 is fixed. If another program holds it when the add-in starts, the palette still works, but the add-in receives no requests. The palette and the Text Commands window of Fusion show a message. Stop the other program, then stop and run the add-in again.
- **Any local program can send a request.** The server listens on 127.0.0.1 only and refuses requests from web pages. It has no other authentication: a request from any program on the computer is accepted. A request can make Fusion load a config file and, with `save`, write that file again.
- **No result for the sender.** A request gets the answer "queued". If the palette is closed, the result is not shown.
- **Checks only.** The add-in runs the checks of the config. It does not run the interference rules. Use `asfinger build` or the web editor for those.
- **A failed check stops the operation.** The palette has no control to build a design while a check fails.
- **The check messages are in the default language of the config**, as on the command line.
- **Options.** The palette has no controls for options. They keep the values that the config stores.
- **User parameters are a record.** The features do not refer to the user parameters, and the add-in writes its values over them at each update. Change a value in the palette, not in the parameter table of Fusion.
- **Meshes.** A mesh that is the whole shape of a part becomes a mesh body, not a solid. A mesh inside a union or a difference is left out, and the result names it.
- **Temporary files.** The add-in writes each placed mesh as an STL file into the temporary folder of the system and does not delete it.
