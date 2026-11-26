# Change the repository

This page is for an agent that changes the code, the site or the documentation in this repository.

## Rules

- Write all comments and docstrings in English.
- Keep `geom.py`, `expr.py`, `frames.py`, `csg.py`, `options.py`, `interference.py`, `mjcf.py` and `__init__.py` free of imports outside the standard library at module level. The browser runs these files in Pyodide.
- When you change how a solid is built in `src/asfinger/mesh.py`, make the same change in `site/src/engine/csg.ts`. Do the same in the other direction.
- Do not rename these names. They are part of file formats or stored data: `ipush_tool.xml`, `ipush_print`, the MJCF body `ipush`, the classes `ipush_col` and `ipush_vis`, the local storage keys `ipush.editor.v3` and `ipush.theme`, the frame names, the config keys and the config file names, the HTTP path `/ipush/apply`, the port 47910, the health reply `ipush-fusion`, and the attribute group `ipush` with its keys in a Fusion design.
- Change the product name only in `PRODUCT_NAME` (`src/asfinger/__init__.py`) and in `PRODUCT` and `EDITOR_NAME` (`site/src/i18n/index.ts`).
- If a change is not meant to change geometry, build the default config before and after it and confirm that every STL file and `ipush_tool.xml` are identical.
- Do not edit a stored `result` of a solved frame by hand. Run `asfinger build CONFIG -o OUT --resolve`.
- When you change a page in `docs/en/`, make the same change in `docs/zh/`. Do the same in the other direction. Write the Chinese text as original Chinese.
- Do not edit generated files: `site/public/py`, `site/public/configs`, `site/public/assets`, `site/public/pyodide`, `site/public/docs`, `site/public/zh`, `site/public/llms.txt`, `site/public/llms-full.txt`, `site/src/content/docs`.
- Do not commit files from `docs/internal/`, and do not link to them from public pages.
- Every file in `hardware/configs/` is published with the site. Do not add a config there unless the user asks for it.
- Add third-party material only with its licence, and record it in `NOTICE`.
- Change the version only in `pyproject.toml`.
- The code in `hardware/cad/fusion/` runs inside Autodesk Fusion. Do not start Fusion, do not load the add-in, and do not change a Fusion document to test it. Run the tests, and tell the user to try the change in Fusion.
- Do not push tags and do not change the deployment settings. Tell the user what to do.

## Code map

| Path | Content |
| --- | --- |
| `src/asfinger/__init__.py` | `Model`: load, set, resolve, check, interference, build. `PRODUCT_NAME`. |
| `src/asfinger/__main__.py` | The command line (`build`, `frames`, `send`). |
| `src/asfinger/expr.py` | Parameter expressions. |
| `src/asfinger/frames.py` | Frame tree and solvers. |
| `src/asfinger/csg.py` | Shape trees. |
| `src/asfinger/options.py` | Options. |
| `src/asfinger/interference.py` | Interference rules. |
| `src/asfinger/mesh.py` | Solids, STL, mass (numpy, manifold3d). |
| `src/asfinger/mjcf.py`, `preview.py`, `build.py` | Writers of the output files. |
| `tests/test_default.py` | Tests of the configs in `hardware/configs/`. |
| `tests/test_docs.py` | Tests of the documentation: same pages in both languages, the example config builds. |
| `tests/test_send.py`, `tests/test_fusion_addin.py` | Tests of `asfinger send`, and of the Fusion add-in with stand-ins for the `adsk` modules. |
| `hardware/configs/`, `hardware/assets/` | Configs and the meshes they import. |
| `hardware/cad/fusion/` | The Fusion add-in (`asFingerAddIn`), its script (`asFingerFromJSON`) and their shared module (`asfinger_fusion`). In each folder, the folder, the `.py` file and the `.manifest` file have the same name. |
| `site/scripts/sync-core.mjs`, `sync-docs.mjs` | Copy the package, the configs and the docs into the site before a build. |
| `site/src/engine/` | The web worker (Pyodide and Manifold). |
| `site/src/editor/`, `site/src/data/`, `site/src/i18n/` | The editor, its catalog, its text. |
| `site/src/pages/`, `site/src/components/` | The landing page and the editor page. |
| `site/astro.config.mjs` | Site address, base path, Starlight sidebar. |
| `docs/en/`, `docs/zh/` | The documentation source. |
| `.github/workflows/` | CI and the deployment of the site. |

## Checks

Run these commands before you finish. All of them must pass.

```bash
uv run ruff check
uv run ruff format --check
uv run pytest
```

If the change touches `site/`, `docs/`, `src/asfinger/` or `hardware/`, also run:

```bash
cd site && npm ci && npm run build
```

## Common tasks

### Add a parameter to a config

1. Add the parameter to `params` in the config, and use it in a frame or a shape.
2. If a solver uses it, run `uv run asfinger build CONFIG -o out/x --resolve` to store the new result.
3. If the editor must show it, add an entry to `site/src/data/pusherParams.ts` with a label in English and in Chinese.
4. Add or change a test in `tests/test_default.py`.
5. Run the checks.

### Add a shape type or a frame feature

1. Add the resolution to `csg.py` or `frames.py`.
2. For a new leaf shape, add it to `mesh.py`, to `mjcf.py` and to `site/src/engine/csg.ts`.
3. Describe it in `docs/en/user/config-file.md` or `frames.md`, and in the Chinese pages.
4. Add a test. Run the checks and the site build.

### Add an interference rule

1. Add the rule to `interference` in the config, with `id`, `msg` (Chinese) and `msg_en`.
2. Add a test that makes the rule fail and a test that the default passes.
3. Add the rule to the table in `docs/en/user/checks.md` and `docs/zh/user/checks.md`.

### Add a documentation page

1. Create the page with the same file name in `docs/en/` and `docs/zh/`.
2. Add the file name to `ORDER` in `site/scripts/sync-docs.mjs`.
3. Link the page from the index page of its section in both languages.
4. Run `uv run pytest` and `cd site && npm run build`.

### Change text in the editor

1. Change the entry in `site/src/i18n/index.ts`, in English and in Chinese.
2. For catalog items and parameter labels, change `site/src/data/catalog.ts` or `pusherParams.ts`.
3. Run `cd site && npm run build`.

### Release a version

1. Change `version` in `pyproject.toml`.
2. Run the checks.
3. Tell the user to create the tag. Do not push tags yourself.
