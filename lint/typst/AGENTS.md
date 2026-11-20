## Typst documents (this repo)

### Checks to run
- `./check` runs every check (hooks, compile) and prints one line per step, with the failing lines
  and a log path when something fails. Paste its summary into the PR's Evidence section.
- `./check --quick` skips the slow steps while you iterate; run the full `./check` before you say
  you're done. `./check --list` shows exactly what runs.
- Documents compile with the pinned Typst and no system fonts; report any warnings.

### Conventions
- The Typst version is pinned in `.typst-version`. Don't upgrade it as part of another change.
- Fonts come from `fonts/` (committed) or Typst's built-in fonts, never system fonts, so the PDF looks
  the same on every machine. Add a font by committing it to `fonts/`.
- Figures and data live next to the document that uses them; diagrams are generated from source where
  possible (for example SVG from a script), not pasted screenshots.
- Generated PDFs go in `build/` and aren't committed unless the person asks for a release copy.
