# Build, test and contribute

This page shows how to set up the repository, which checks to run, and how the documentation is built.

## Set up

You need [uv](https://docs.astral.sh/uv/) for the Python package and Node.js 22 or later for the site.

```bash
git clone https://github.com/asEmbodiedAISyst/asFinger.git
cd asFinger
uv sync                      # the package and the development tools
cd site && npm ci            # the site
```

## Checks for the package

Run these commands from the root of the repository. All of them must pass.

```bash
uv run ruff check
uv run ruff format --check
uv run pytest
```

`uv run ruff format` applies the format. The tests build the configs in `hardware/configs/` and load the result in MuJoCo. They also build the example of the documentation and compare the page lists of the two languages. The tests of `asfinger send` and of the Fusion add-in use a local HTTP server and stand-ins for the `adsk` modules. They do not start Fusion, so a change to `hardware/cad/fusion/` must also be tried in Fusion by hand.

The tests in `tests/robot/` run the robot-side tools in the simulator. They need the dependency group `robot` and are skipped without it:

```bash
uv sync --group robot --python 3.12
uv run --group robot pytest tests/robot
```

No test connects to an arm or a phone. A change to `robot/` that can alter a motion must also be run on the real arm by the owner of the setup, with an operator at the power switch. Say in the pull request what was run on the arm and what was not. Tests that need the raw calibration data or the pictures of the real scene in `calibration/data/` run only where those files exist. The same applies to the tests that need the arm meshes (`uv run python sim/fetch_arm_meshes.py`) or a GL context: set `ASFINGER_TEST_GL` to a MuJoCo GL backend, for example `glfw` on macOS, to run the rendering tests.

When you change the generator, compare the outputs before and after the change. A change that is not meant to change geometry must leave the STL files and `ipush_tool.xml` identical, byte for byte:

```bash
uv run asfinger build hardware/configs/iphone17pro_default.json -o out/after
```

## The site

```bash
cd site
npm run dev        # sync, then a development server on http://localhost:4321
npm run build      # sync, then the static site in site/dist
npm run preview    # serve site/dist
```

`npm run sync` runs two scripts before each build:

- `scripts/sync-core.mjs` copies the pure-Python modules of `src/asfinger`, the configs in `hardware/configs`, the meshes they import, and the Pyodide runtime into `site/public/`.
- `scripts/sync-docs.mjs` copies the documentation into the content folder of Starlight and writes `llms.txt` and `llms-full.txt`.

All these copies are generated and ignored by git. Do not edit them.

Every config in `hardware/configs/` is published with the site, and so is each mesh that a config imports.

The site address and the base path come from two environment variables. The deployment sets them. To test the published layout on your computer:

```bash
SITE_URL=https://asembodiedaisyst.github.io BASE_PATH=/asFinger/ npm run build
```

The user interface text of the editor is in `site/src/i18n/index.ts`. The product name is defined there once (`PRODUCT`, `EDITOR_NAME`).

## Documentation

The documentation source is `docs/en/` and `docs/zh/`. The two trees have the same files. Each tree has `user/`, `developer/` and `agents/`.

Rules:

- Change both languages together. A test fails when the two trees do not have the same pages.
- Write each language in its own style. Do not translate sentence by sentence.
- Use the terms of the [glossary](../glossary.md). Add a new term to the glossary in both languages.
- Start each page with one `# Title` and a short first paragraph. The site uses them as the page title and the description.
- Link to other pages with relative links to the `.md` files. The site build converts them.
- Write a defect or a risk on the page of the feature that it belongs to.
- Internal notes go to `docs/internal/`, which git ignores. Public pages do not refer to them.

A new page also needs an entry in the list `ORDER` of `site/scripts/sync-docs.mjs`, which sets the order in the sidebar.

## Continuous integration

| Workflow | Runs on | Function |
| --- | --- | --- |
| `.github/workflows/ci.yml` | push to `main`, pull request | ruff and pytest for the package on each supported Python version, the robot-side tests in the simulator on one Python version, and a build of the site. |
| `.github/workflows/pages.yml` | push to `main` that changes the site, the docs, the package or the hardware inputs | Builds the site and deploys it to GitHub Pages. |

## Send a change

1. Make a branch.
2. Make the change, with tests for new behaviour.
3. Update the documentation in both languages.
4. Run the checks for the package, and `npm run build` in `site/` if the change touches the site, the docs, the package or the configs.
5. Open a pull request. Say what changed, and whether the outputs of the default config changed.

Comments and docstrings are in English.
