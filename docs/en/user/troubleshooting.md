# Troubleshooting

Each entry gives a message or a symptom, its cause and the correction.

## Command line

**`[warn] P_phone: saved result is stale (inputs changed); run with --resolve to update`**

You changed a parameter that the phone solver uses, but the build used the stored pose. Add `--resolve` to the command. See [Frames](frames.md#solved-frames).

**`[check] ...` after a parameter change**

A check failed. The message names the frame, its coordinate and the permitted range. The usual cause in the default config is a phone that sits too low after you made the rod shorter. Increase `phone_flange_angle` or `distance`.

**`[interference] ... (phone_vs_body: 8632.7 mm³)`**

Two solids overlap. The name before the colon is the rule, and the number is the overlap volume. The message says which parameter to change. The table of rules is in [Checks and interference rules](checks.md#the-rules-of-the-default-config).

**The interference messages are in Chinese**

The command line prints the default message of each rule. Use the rule name in the message, or call `m.interference(lang='en')` in Python.

**`KeyError: 'unknown parameter ...'` or `KeyError: 'unknown option ...'`**

`--set` and `--option` accept only names that exist in the config. List the parameters with `python -c "from asfinger import Model; print(list(Model.load('CONFIG').cfg['params']))"`.

**`ExprError: unknown name ...` or `unsupported syntax ...`**

An expression uses a name that is not a parameter, or syntax that is not allowed. The permitted syntax is in [The config file](config-file.md#parameters-and-expressions).

**`ValueError: ... is not a closed (manifold) solid`**

An imported mesh has holes or open edges. Repair the mesh in a mesh tool and export it again.

**`FileNotFoundError` for a file in `assets/`**

The config looks for `assets/` beside its own folder, not in the current directory. Put the config in a folder that has `assets/` as its neighbour, or write an absolute path in `file`.

**`frame cycle at ...` or `frame X refers to unknown frame Y`**

The frame tree has a loop, or a frame names a parent or a target that does not exist.

**`Fusion add-in not reachable on port 47910`**

The command `asfinger send` sends a config to an add-in in Autodesk Fusion. The add-in is not in this repository yet. Use `asfinger build`.

## Output

**`report.json` gives `"bodies": 2` or more for a print set**

The parts of the print set do not touch, so the file would print as separate pieces. Examine the parameters that position the phone holder.

**`preview.html` is empty**

The page needs an internet connection to load three.js. It also needs a camera named `C_main`. A config without that camera, or a build with `--option phone=0`, gives an empty page. Use the web editor or a mesh viewer for the STL files.

**The printed pusher does not fit the phone case**

`back_to_mount` is the back thickness of the case. Measure your case and set the parameter. See [Frames](frames.md#known-limits-of-the-phone-frames).

## Web editor

**"The editor needs a wide desktop browser window (≥ 1100 px)."**

Make the window wider, or use a desktop computer.

**"Loading the geometry engine" stays on the screen**

The first load downloads about 13 MB. If the message stays, examine the network connection and load the page again.

**The STL export buttons are disabled**

A check or an interference rule fails. Read the message, change the parameter that it names, and export again. The config export stays available.

**My parameters are gone**

The editor stores them in the local storage of one browser. A different browser, a private window or cleared site data starts from the defaults. Export the config to keep your work.
