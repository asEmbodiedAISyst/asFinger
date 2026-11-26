# Checks and interference rules

A config can contain two types of tests. A check limits the position of a frame. An interference rule finds solids that overlap. This page describes both, and lists what they do not find.

## Checks

A check compares one coordinate of a frame, in the root frame, with a minimum or a maximum.

```json
"checks": [
  {"frame": "J_foot", "axis": "z", "min": "plate_t",
   "msg": "手机太低，支撑条会穿到法兰面以下", "msg_en": "Phone too low: the spine would pass below the flange face."}
]
```

`axis` is `x`, `y` or `z` (default `z`). `min` and `max` are expressions. `msg` is the default message. `msg_en` is the English message.

`asfinger build` and `asfinger frames` print each failed check as a line that starts with `[check]`. In Python, `m.check()` returns the messages, and `m.check(lang='en')` returns the English ones.

## Interference rules

A rule names two sides, `a` and `b`. It fails when the volume of their overlap is larger than `tol_mm3` (default 1 mm³).

```json
"interference": [
  {"id": "phone_vs_body", "a": "phone", "b": "tool_body", "msg": "...", "msg_en": "..."},
  {"id": "holder_vs_rod", "a": "holder", "b": {"part": "tool_body", "only": ["rod", "tip"]}},
  {"id": "sight_to_tip",
   "a": {"sight": {"from": "C_main", "to": "T_tip", "stop_before": "rod_D/2 + 1", "r": 0.5}},
   "b": [{"part": "tool_body", "only": ["adapter", "beam_mitred", "spine_mitred"]}, "holder", "phone"],
   "tol_mm3": 0.3}
]
```

A side can be:

| Form | Meaning |
| --- | --- |
| `"phone"` | A whole part. |
| `{"part": "tool_body", "only": [names]}` | Only the named nodes of a part. |
| `{"part": "tool_body", "skip": [names]}` | A part without the named nodes. |
| `{"sight": {"from": F, "to": F, "r": r, "stop_before": d}}` | A thin cylinder between two frame origins: a line of sight. |
| `{"csg": node, "frame": F}` | A solid that exists only for the test, for example a screw head or the space for a tool. |
| a list of these forms | Their union. |

A rule can also have:

- `enabled`: an expression. The rule is skipped when it is 0.
- `level`: `"error"` (default) or `"warn"`. An error is something that cannot be built. A warning is an inconvenience, for example a screw that needs a short hex key.

A rule is skipped when one of its parts or frames is switched off by an option.

`asfinger build` prints errors as `[interference]` lines and warnings as `[warning]` lines, and writes both to `report.json`. In Python, `m.interference()` returns the errors and `m.interference(level='warn')` the warnings. The web editor evaluates the same rules, shows the overlap in red, and blocks the STL export while an error exists.

> **Language of the messages.** The command line prints `msg`. In the configs of this repository, `msg` is Chinese and `msg_en` is English. For English messages, use `m.check(lang='en')` and `m.interference(lang='en')` in Python, or read the rule `id` in the message.

## The rules of the default config

| Rule | Level | Fails when |
| --- | --- | --- |
| `phone_vs_body` | error | The pusher passes through the phone. |
| `phone_vs_holder` | error | The phone overlaps its holder (`back_to_mount` too small). |
| `holder_vs_rod` | error | The rod passes through the holder. |
| `sight_to_tip` | error | A solid blocks the line from the main camera to the tip. |
| `adapter_vs_body` | error | The pusher overlaps the flange adapter. |
| `screw_heads` | error | A screw head of the base overlaps the pusher (only with `mount_screws = 2`). |
| `screw_access` | error | No room for a hex key above a screw (only with `mount_screws = 2`). |
| `screw_driver` | warn | A straight driver cannot reach a screw (only with `mount_screws = 2`). |

The one check, on `J_foot`, fails when the phone is so low that its support would pass below the flange face.

## What the tests do not find

- **Only the listed pairs are tested.** Two solids that are in no rule can overlap without a message.
- **Small overlaps pass.** An overlap below `tol_mm3` is not reported. Two faces that only touch have no overlap volume.
- **Clearance is not tested.** A rule reports an overlap. It does not report a gap that is too small for assembly or for printing tolerance.
- **The line of sight is one thin line.** `sight_to_tip` tests a cylinder of 0.5 mm radius from `C_main` to the tip. It does not test the full field of view, and it does not test the other cameras.
- **The robot is not part of the model.** No rule tests the pusher or the phone against the links of the arm or against the table.
- **Printing is not tested.** Overhangs, wall thickness and strength are not examined. The phone holder snaps are brittle in matte PLA. Print them in PETG, or flat as a separate part.
- **A stale solved frame makes the tests wrong.** The tests use the stored pose of the phone. See [Frames](frames.md#solved-frames).
- **The phone is a box.** The part `phone` is a stand-in: a box with the outer dimensions of the iPhone 17 Pro, and a ring for the main lens. It has no case and no full camera bump.
