# asFinger design profile

The look of the site and the editor comes from `tokens.css`; change values there, not in components.

| Area | Tokens | Notes |
|---|---|---|
| Palette | `--ink*`, `--paper`, `--surface*`, `--line` | Near-black ink on warm off-white; one accent only. |
| Accent | `--accent`, `--accent-soft`, `--accent-ink` | Selection, primary action, focus ring. Nothing else is coloured. |
| Status | `--ok`, `--warn`, `--danger` | Check results and export state. |
| 3D | `--viewport-bg`, `--grid`, `--axis-x/y/z`, `--part-*` | Frames always use RGB = XYZ. Printed parts grey-blue, reference parts light grey, robots lighter still. |
| Type | `--font-sans`, `--font-mono`, `--fs-*` | System fonts (no web-font download). Numbers and frame names in mono. |
| Shape | `--radius*`, `--space-*`, `--shadow`, `--shadow-float` | Soft 10 px radius, flat surfaces, a single light shadow; `--shadow-float` only for panels over the 3D view. |
| Layout | `--float-gap`, `--header-h`, `--rail-w`, `--left-w`, `--right-w` | The editor is the 3D view with floating pieces: top strip, Config rail and panel, Inspect panel. |

Logo: `src/components/logo.svg`, a hand with only the index finger raised, drawn as a single-weight
round-capped black line (stroke 3.2 on a 64 grid, `currentColor`). Keep it monochrome.

Dark mode follows the system unless `<html data-theme="light|dark">` is set. The editor's top strip has the switch (system / light / dark, `src/theme.ts`); a choice is kept per browser under `ipush.theme` and applied by `Base.astro` before the first paint, on every page.
