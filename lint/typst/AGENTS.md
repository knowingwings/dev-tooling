## Typst documents (this repo)

### Checks to run
1. `typstyle -i <changed .typ files>`
2. `pre-commit run typst-compile --hook-stage pre-push --all-files`: compiles every document in
   `.typst-entries` to `build/` with the pinned Typst and no system fonts. Report any warnings.

### Conventions
- The Typst version is pinned in `.typst-version`. Don't upgrade it as part of another change.
- Fonts come from `fonts/` (committed) or Typst's built-in fonts, never system fonts, so the PDF looks
  the same on every machine. Add a font by committing it to `fonts/`.
- Figures and data live next to the document that uses them; diagrams are generated from source where
  possible (for example SVG from a script), not pasted screenshots.
- Generated PDFs go in `build/` and aren't committed unless the person asks for a release copy.
