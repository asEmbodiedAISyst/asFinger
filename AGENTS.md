# AGENTS.md

Instructions for coding agents that work in this repository.

- To change the code, the site or the documentation, read [`docs/en/agents/developing.md`](docs/en/agents/developing.md) first.
- To use the package for a user, read [`docs/en/agents/using.md`](docs/en/agents/using.md).
- Before you finish, run `uv run ruff check`, `uv run ruff format --check` and `uv run pytest`. All three must pass. If the change touches `site/`, `docs/`, `src/asfinger/` or `hardware/`, also run `npm run build` in `site/`.
- Write all comments and docstrings in English.
- When you change a page in `docs/en/`, make the same change in `docs/zh/`. Do the same in the other direction.
- Do not rename `ipush_tool.xml`, `ipush_print`, the frame names or the config keys. They are part of file formats.
