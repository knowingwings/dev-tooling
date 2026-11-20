#!/usr/bin/env bash
# Compile a repo's Typst documents the same way on every machine (pre-commit hook `typst-compile`).
#
# Entry documents: listed one per line in .typst-entries (comment lines start with #), or every
# main.typ in the repo if that file doesn't exist. Output goes to build/, which should be gitignored.
#
# Reproducible by default:
#   - .typst-version pins the compiler (e.g. 0.15.1); a different local version is an error,
#     because layout can change between releases
#   - system fonts are ignored; fonts come from fonts/ (committed) plus Typst's built-in fonts,
#     so a document renders the same on Linux, macOS and Windows
#     (set TYPST_SYSTEM_FONTS=1 to allow system fonts for a quick local preview)
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

entries=()
if [[ -f .typst-entries ]]; then
  while IFS= read -r line; do
    [[ -z "${line// }" || "$line" == \#* ]] && continue
    entries+=("$line")
  done < .typst-entries
else
  while IFS= read -r f; do entries+=("$f"); done < <(git ls-files '*main.typ')
fi
[[ ${#entries[@]} -eq 0 ]] && { echo "typst_compile: no entry documents (add .typst-entries)"; exit 0; }

command -v typst >/dev/null || { echo "typst not found: see docs/SETUP.md (Typst) to install it" >&2; exit 2; }

if [[ -f .typst-version ]]; then
  want="$(tr -d '[:space:]' < .typst-version)"
  have="$(typst --version | awk '{print $2}')"
  if [[ "$have" != "$want" ]]; then
    echo "This repo pins Typst $want (.typst-version) but you have $have." >&2
    echo "Install $want (e.g. 'typst update $want'), or bump .typst-version in its own commit and check the PDFs." >&2
    exit 1
  fi
fi

font_args=()
[[ "${TYPST_SYSTEM_FONTS:-0}" == 1 ]] || font_args+=(--ignore-system-fonts)
[[ -d fonts ]] && font_args+=(--font-path fonts)

status=0
for doc in "${entries[@]}"; do
  out="build/${doc%.typ}.pdf"
  mkdir -p "$(dirname "$out")"
  log="$(mktemp)"
  if typst compile --root . "${font_args[@]}" "$doc" "$out" 2> "$log"; then
    if grep -q "unknown font family" "$log"; then
      cat "$log" >&2
      echo "FAIL $doc: uses a font that isn't in fonts/ or built into Typst, so it renders differently" >&2
      echo "     on each machine. Commit the font file to fonts/, or use a built-in font" >&2
      echo "     (Libertinus Serif, New Computer Modern, DejaVu Sans Mono)." >&2
      status=1
    else
      cat "$log" >&2
      echo "ok  $doc -> $out"
    fi
  else
    cat "$log" >&2
    status=1
  fi
  rm -f "$log"
done
exit $status
