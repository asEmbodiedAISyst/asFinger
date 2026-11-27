# Developer guide

This guide is for people who want to understand or change the project.

| Page | Content |
| --- | --- |
| [Architecture](architecture.md) | How one config becomes frames, solids and files, in Python and in the browser. |
| [Design decisions](decisions.md) | The main decisions and the reasons for them. |
| [Build, test and contribute](contributing.md) | Set up the repository, run the checks, write documentation, send a change. |
| [State and roadmap](roadmap.md) | What exists, what is known to be weak, and what comes next. |

The repository layout:

| Path | Content |
| --- | --- |
| `src/asfinger/` | The generator, a Python package. |
| `tests/` | The tests of the generator and of the documentation. |
| `hardware/configs/` | The configs of the real tool. |
| `hardware/assets/` | The meshes that the configs import. |
| `hardware/cad/fusion/` | The add-in and the script for Autodesk Fusion. |
| `site/` | The website: landing page, editor and the documentation site. |
| `docs/en/`, `docs/zh/` | The documentation source, in English and in Chinese. |
