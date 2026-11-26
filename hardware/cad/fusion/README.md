# asFinger in Autodesk Fusion

This folder holds the Fusion add-in of asFinger. It builds a config as a parametric design and updates that design in place.

| Folder | Content |
| --- | --- |
| `asFingerAddIn/` | The add-in: a palette with the parameters of a config, and an HTTP server on 127.0.0.1:47910 that receives configs from `asfinger send`. |
| `asFingerFromJSON/` | A script that builds one `resolved.json` in a new document. |
| `asfinger_fusion/` | The module that both use to make and to change the Fusion features. |

To install the add-in, open Utilities > Add-Ins > Scripts and Add-Ins in Fusion, click `+` and select the folder `asFingerAddIn`. Stop the earlier iPush add-in first, if you have it. Leave the folders in the repository: the add-in imports the package from `src/asfinger`.

The guide is in [`docs/en/user/fusion.md`](../../../docs/en/user/fusion.md) ([website](https://asembodiedaisyst.github.io/asFinger/docs/user/fusion/), [中文](https://asembodiedaisyst.github.io/asFinger/zh/docs/user/fusion/)).

`asFingerAddIn/settings.json` is written at run time and is not in git.
