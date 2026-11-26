# Architecture

The generator is a pipeline with one input, the config, and several outputs. The web editor runs the first half of the same pipeline in the browser.

## The pipeline

```text
config (JSON)
   │  expr.py        evaluate the parameters
   │  options.py     drop the frames and parts of options that are off
   │  frames.py      resolve the frame tree, run the solvers
   │  csg.py         resolve each shape tree: every leaf gets a pose in the root frame and numeric sizes
   ▼
resolved model      (pure Python up to here: no numpy, no native code)
   │  mesh.py        build solids with manifold3d, clean them, read and write STL, mass properties
   │  interference.py  select the solids of each rule; mesh.py intersects them
   ▼
build.py            write resolved.json, print/*.stl, meshes/*.stl, ipush_tool.xml (mjcf.py), preview.html (preview.py), report.json
```

`Model` in `__init__.py` is the public entry point. `__main__.py` is the command line.

| Module | Function | Needs |
| --- | --- | --- |
| `geom.py` | Vectors, rotation matrices, quaternions and the transform class `Tf`. | standard library |
| `expr.py` | Safe evaluation of parameter expressions with the `ast` module. | standard library |
| `frames.py` | Frame tree, rotation forms, `pos_from`, `z_from`, the solver `coplanar_look_at`, the stale-result hash. | `geom`, `expr` |
| `options.py` | The pruned view of a config when options are off. | standard library |
| `csg.py` | Shape trees: resolution, collision leaves, JSON output. | `geom`, `expr`, `frames` |
| `interference.py` | Interference rules: which resolved trees to intersect. | `geom`, `expr`, `csg` |
| `mjcf.py` | The MJCF writer. | `expr` |
| `mesh.py` | Solids, STL input and output, mass and inertia. | numpy, manifold3d |
| `preview.py` | The HTML preview. | numpy |
| `build.py` | Runs all the steps and writes the files. | all of the above |

## The resolved model

`Model.resolve()` returns a dictionary:

| Key | Content |
| --- | --- |
| `P` | Every parameter as a number. |
| `world`, `local` | For each frame, its pose in the root frame and in its parent (`Tf`). |
| `info` | For each frame, its source (`module`, `manual` or `solved`) and the solver report. |
| `parts` | The parts, each with its resolved shape tree and its collision leaves. |
| `cfg` | The config as evaluated: the pruned view when options are off. |

A resolved leaf has a type, numeric sizes and a pose `T` in the root frame. Every backend reads this one structure: the mesh builder, the MJCF writer, the interference rules and the browser. `Model.resolved_json()` is the same data as plain JSON, with poses as position and quaternion.

## The solver and stale results

A solved frame stores `solve` (the intent) and `result` (the pose and a hash of the solver inputs). `resolve_frames` computes the hash again on each run. It uses the stored result unless `resolve=True`. If the hash differs, it reports the result as stale. This makes a build repeatable: the same config file gives the same files, also when a solver changes later.

## The browser

The editor in `site/` runs the pure-Python half of the pipeline and replaces the mesh backend.

```text
site/scripts/sync-core.mjs      copies src/asfinger/*.py (the pure modules), hardware/configs/*.json and the meshes
                                they import into site/public/, and the Pyodide runtime from node_modules
site/src/engine/worker.ts       a web worker: Pyodide imports asfinger and returns resolved_json, the check messages
                                and the config with new solver results
site/src/engine/csg.ts          builds the resolved trees with manifold-3d (WebAssembly); mirrors mesh.py
site/src/engine/client.ts       the main-thread handle; only the newest solve request is kept
site/src/editor/                the React user interface and the three.js view
site/src/data/                  the catalog of carriers, adapters and cameras, and the labels of the parameters
```

The list `PURE` in `sync-core.mjs` names the modules that are copied. A module in that list must not import numpy or manifold3d. The interference rules reach the browser as resolved trees inside `resolved_json`, and `worker.ts` intersects them.

`csg.ts` and `mesh.py` are two implementations of one step. A change in one must be made in the other.

## The documentation site

`site/scripts/sync-docs.mjs` copies `docs/en` and `docs/zh` into the content folder of Starlight, rewrites the links between pages, and writes `llms.txt` and `llms-full.txt`. The landing page and the editor are plain Astro pages in `site/src/pages`. See [Build, test and contribute](contributing.md#documentation).

## Names kept from the earlier project name

The project was named iPush before it became asFinger. These names are part of file formats or stored data and did not change: the output files `ipush_tool.xml` and `ipush_print.stl`, the print set name `ipush_print`, the MJCF body `ipush` and the classes `ipush_col` and `ipush_vis`, the local storage keys `ipush.editor.v3` and `ipush.theme`, the name of the exported config file, and the path `/ipush/apply` of the `send` command. The name that people see is defined once in the package (`PRODUCT_NAME`) and once in the site (`PRODUCT` and `EDITOR_NAME` in `site/src/i18n/index.ts`).
