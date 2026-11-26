# asFinger site

Static Astro site: a landing page (`/`), the in-browser editor (`/editor`) and the documentation (`/docs/`,
served by Starlight). Chinese pages are under `/zh/`.

## Run

```bash
npm ci
npm run dev      # sync, then http://localhost:4321
npm run build    # sync, then a static site in dist/
npm run preview
```

`npm run sync` runs two scripts before `dev` and `build`:

- `scripts/sync-core.mjs` copies the pure-Python modules of `../src/asfinger`, the configs in
  `../hardware/configs`, the meshes they import and the Pyodide runtime into `public/`.
- `scripts/sync-docs.mjs` copies `../docs/en` and `../docs/zh` into `src/content/docs/` (the Starlight pages) and
  into `public/` (the Markdown originals), and writes `public/llms.txt` and `public/llms-full.txt`.

Both read the repo one level up (`..`); set `ASFINGER_ROOT=/path/to/repo` if the site lives elsewhere.
Everything they write is generated and git-ignored.

## Documentation pages

The documentation is written in `../docs`, never here. A page's title is its first `# heading` and its
description is the first paragraph. `ORDER` in `scripts/sync-docs.mjs` sets the order in the sidebar; the three
sidebar sections are in `astro.config.mjs`. The colours of the documentation pages are in `src/styles/docs.css`.

## How the editor works

- `src/engine/worker.ts` runs in a Web Worker. Pyodide runs the same `asfinger` Python as the command line
  (parameters, frame solving, CSG trees); manifold-3d (WASM) turns the trees into meshes and STL.
  A solve takes about 0.1–0.3 s; the first load takes a few seconds.
- `src/engine/client.ts` is the main-thread handle. `solve()` keeps only the newest request, so dragging a slider
  never queues stale work.
- `src/editor/scene.ts` is the three.js view (imperative, created once). `Editor.tsx` holds the state; the panels
  only render it.
- `src/data/catalog.ts` lists the groups (carrier, flange adapter, pusher, tip, camera) and their items. Add a
  group or an item there and the UI picks it up. Values marked `verify: true` show as "to verify".
- Who decides the pusher base: an adapter's `sets` fixes the hole pattern on its tool side, its height and the
  screw direction (`mount_screws`), and its `option` switches the config option `adapter`. With the adapter
  "None" the carrier's `sets` (its own flange pattern, `src/data/flanges.ts`) applies instead. A carrier also
  gives the default mounting angle `mountRot` (config parameter `mount_rot`), chosen so that every arm carries
  the phone on top, and `direct.defaults` for what changes when the pusher is bolted on directly. Adapters list
  the carriers they fit in `fits`; picking a carrier picks its `defaultAdapter`.
- `src/data/pusherParams.ts` gives each pusher parameter a label, unit, range, section and owner.
- The user's selection and edits are kept in the browser's localStorage only.

## Layout names

The 3D view fills the window and everything else floats over it. Three names are used in discussion:

- **View**: the 3D view (`CenterPanel`, `.stage`) with the selection bar in the top strip (`SelectionBar`).
- **Config**: on the left, a rail with one button per group (always visible) and, beside it, the cards of the group
  being configured (`LeftPanel`; closed until a rail button is clicked, Esc or the same button closes it).
- **Inspect**: on the right, Info on top and Params below, with a draggable splitter limited to 1/3 .. 2/3 of the
  height (double-click resets it). Closed at first; the "Parameters & info" tab opens it (`.right` with `InfoPanel`
  and `ParamsPanel`).

What the view shows: Config always works on the full assembly. Picking a group or a card moves the camera to that
part (`SceneContent.focus`, the camera keeps its direction), outlines it in the accent colour (three.js
`OutlinePass`, only while something is outlined; the tip gets an unseen ball as its outline shape) and Inspect is
then about it. A chip of the selection
bar shows that part alone (`solo` in `Editor.tsx`, the old per-group views); the same chip or "Full assembly" goes
back. The view keeps the model in the middle of what the open panels leave free (`SceneView.setInsets`).

In the full assembly the pusher is what stays put: its base frame `F_mount`, at the carrier's default mounting
angle, always sits at `TOOL_POSE` (`scene.ts`, the pose the reBot holds it in) and the carrier is placed under it.
Changing the carrier or the adapter therefore changes only that; turning `mount_rot` away from the default turns
the pusher on the flange. The grid is the surface the arm stands on.

Frame labels follow the unified convention for the phone side: `device` (the config's `P_phone`: x right, y to the
top of the phone, z out of the screen) and `cam_main_optical` (`C_cv`: OpenCV, x image right, y image down, z along
the view). The config keeps its own frame names; `FRAME_LABEL` in `scene.ts` maps them.

Parameters marked `advanced` in `src/data/pusherParams.ts` are hidden until "Advanced" is ticked; for the rod only
its length and tilt are shown at first.

## Languages

English is the default at `/` and `/editor`; Chinese lives at `/zh/` and `/zh/editor`. Both pages per language
are one-liners over `src/components/Home.astro` and `EditorPage.astro`. All editor text is in `src/i18n/index.ts`
(`UI`, used as `t('key')`); the product name and the editor's name are the two entries `PRODUCT` and
`EDITOR_NAME` there, and nothing else spells them out; catalog and parameter data use `Txt` (`{ en, zh }` or a plain string), shown with `tx()`.
Check messages come from the config (`msg_en`, `msg` for Chinese) through `Model.check(R, lang)`.
To add a language, add it to `LANGS` and give every `UI` entry and `Txt` value that key.

## Arm models

`public/arms/<id>.glb` are baked, posed and in mm, by `scripts/bake-arms.py` from MuJoCo Menagerie (FR3, UR5e:
all of their visual triangles, about 230k and 120k) and from the full-detail reBot meshes of
Seeed-Projects/reBot-DevArm (`Rebot_Arm_description/RS/meshes`, about 590k triangles without the gripper, reduced
to 320k). Materials keep their metallic / roughness values; the GLBs are quantized and meshopt-compressed
(1.1 to 3.7 MB each), and `scene.ts` gives the loader the meshopt decoder. The flange pose, pose name and source
go to `src/data/arms.json`; the scene attaches the config's root frame `F_robot` (the robot's own flange) there.
All three arms are posed with the flange pitched 30° below horizontal, so one mounting rule (phone on top) gives
each its default `mountRot`, and with the pusher base face 265.4 mm above the arm base (where the reBot holds it
in the pose HOME_QPOS), so the pusher and the ground stay where they are when the arm is swapped. Licences of the meshes are in `public/arms/licenses/`.
A carrier without a GLB falls back to the drawn placeholder arm.

    pip install mujoco trimesh fast-simplification scipy
    npm i --no-save @gltf-transform/cli
    python scripts/bake-arms.py --menagerie ../mujoco_menagerie --rebot path/to/RS/rebot_no_tool.xml \
        --gltf-transform node_modules/.bin/gltf-transform

For `--rebot`, copy `scripts/rebot_no_tool.xml` next to the `meshes` folder of reBot-DevArm's
`Rebot_Arm_description/RS` and pass that path. It is an MJCF of the reBot arm without a tool and without the
gripper connector mesh (`link6.STL`): the flange frame is the `link6` body itself, and the editor draws the
connector as the flange adapter.
`--only ur5e` re-bakes one arm and keeps the other entries of `arms.json`. `crease` (per arm, degrees) is the edge
angle above which shading stays hard; the UR5e needs 50 because its tubes have about 10 sides.

The view is lit by three.js' `RoomEnvironment` plus a fill and a key light, with neutral tone mapping, so the metal
and plastic of the arm materials read as such while the part colours stay as designed.

## Look

All colours, fonts and sizes are tokens in `src/styles/tokens.css`; see `src/styles/DESIGN.md`.
Logo: `src/components/logo.svg` (also `public/favicon.svg`).

## Deploy

`dist/` is a plain static site. The build needs the rest of the repo (for `src/asfinger`, `hardware` and `docs`),
so build from a checkout of the whole repo.

Where the site is served is set at build time (`astro.config.mjs`): `SITE_URL` (default
`https://asembodiedaisyst.github.io`) and `BASE_PATH` (default `/`). Every link and every file the editor loads
goes through the base path, so the site also works under a sub-path. The published site is built with

    SITE_URL=https://asembodiedaisyst.github.io BASE_PATH=/asFinger/ npm run build

**GitHub Pages**: `.github/workflows/pages.yml` in the repo root builds and publishes on every push to `main` that
touches the site, the docs, `src/asfinger` or the hardware inputs (or by hand: Actions > "Deploy site to GitHub
Pages" > Run workflow). Set Settings > Pages > Source to "GitHub Actions" once. The workflow takes the address and
the sub-path from the Pages settings, so a custom domain set there needs no change here.

`npm run build` writes about 27 MB (Pyodide 13 MB, arm models 7 MB); nothing is loaded from a CDN at run time.
