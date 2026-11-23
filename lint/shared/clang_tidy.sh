#!/usr/bin/env bash
# Run clang-tidy using every compile_commands.json found under the build dir(s).
#
#   clang_tidy.sh                 # all project sources (run from the project root)
#   clang_tidy.sh src/foo.cpp ... # just these files (the pre-push hook passes changed files)
#
# ROS 2:    colcon build puts one compile_commands.json per package in build/<pkg>/
# Firmware: usually a single build/compile_commands.json
#
# Override tool names if your distro suffixes them, e.g.
#   RUN_CLANG_TIDY=run-clang-tidy-20 CLANG_TIDY=clang-tidy-20 pre-commit run clang-tidy --hook-stage pre-push --all-files
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
BUILD_DIR="${BUILD_DIR:-$ROOT/build}"
CLANG_TIDY="${CLANG_TIDY:-clang-tidy}"
# Runner name differs by install: apt = run-clang-tidy(-NN), pip/uv wheel = run-clang-tidy.py
# Use the runner installed alongside the clang-tidy binary: a runner from another LLVM version fails.
if [[ -z "${RUN_CLANG_TIDY:-}" ]]; then
  CT_DIR="$(dirname "$(command -v "$CLANG_TIDY")")"
  for c in run-clang-tidy run-clang-tidy.py; do
    [[ -x "$CT_DIR/$c" ]] && { RUN_CLANG_TIDY="$CT_DIR/$c"; break; }
  done
fi

mapfile -t DBS < <(find "$BUILD_DIR" -name compile_commands.json -not -path '*/CMakeFiles/*' 2>/dev/null)
if [[ ${#DBS[@]} -eq 0 ]]; then
  echo "No compile_commands.json under $BUILD_DIR." >&2
  echo "ROS 2:    colcon build --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON" >&2
  echo "Firmware: cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON" >&2
  exit 2
fi

# Windows (Git Bash) support, added 2026-11-20. run-clang-tidy matches its file filter against
# paths it makes with os.path.abspath, which on Windows have \ separators and a drive letter (C:\x), while
# Git Bash gives /c/x or C:/x. So: turn paths into C:/x form when cygpath exists (Git Bash, MSYS2,
# Cygwin), build every filter so that / in a path matches / or \, and stop MSYS rewriting the arguments
# of the native runner. On Linux and macOS there is no cygpath and nothing changes.
native_path() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi
}
path_re() {   # a path as a regex: special characters escaped, / matching / or \
  native_path "$1" | sed -e 's/[.[\*^$()+?{|]/\\&/g' -e 's#/#[\\\\/]#g'
}
export MSYS2_ARG_CONV_EXCL='*'
S='[\\/]'

# File filter: given files, or everything in the repo except generated/vendored dirs.
if [[ $# -gt 0 ]]; then
  FILTER=()
  for f in "$@"; do
    [[ "$f" =~ \.(c|cc|cpp|cxx)$ ]] || continue   # headers are checked via the .c/.cpp that include them
    FILTER+=("$(path_re "$(realpath "$f")")\$")
  done
  [[ ${#FILTER[@]} -eq 0 ]] && exit 0
else
  FILTER=("^$(path_re "$ROOT")${S}(?!(build|install|log|third_party|vendor|Drivers)${S})")
fi

count_matching_entries() {
  local py c dbs=()
  for c in python3 python; do "$c" -c '' >/dev/null 2>&1 && { py="$c"; break; }; done
  [[ -n "${py:-}" ]] || { echo unknown; return; }
  for c in "${DBS[@]}"; do dbs+=("$(native_path "$c")"); done
  "$py" - "${#FILTER[@]}" "${FILTER[@]}" "${dbs[@]}" <<'EOF'
import json, os, re, sys
n = int(sys.argv[1])
pattern = re.compile("|".join(sys.argv[2 : 2 + n]))
names = set()
for db in sys.argv[2 + n :]:
    with open(db, encoding="utf-8") as f:
        for e in json.load(f):
            name = e["file"]
            if not os.path.isabs(name):
                name = os.path.normpath(os.path.join(e["directory"], name))
            if pattern.search(name):
                names.add(name)
print(len(names))
EOF
}

if [[ "$(count_matching_entries)" == 0 ]]; then
  if [[ $# -gt 0 ]]; then what="none of the files to check is"; else what="no file under $ROOT is"; fi
  {
    echo "clang-tidy: $what in a compile_commands.json under $BUILD_DIR, so nothing would be checked."
    echo "Usual cause: that build was configured from another checkout of this repo (a git worktree or"
    echo "another clone), or the files are new since the last build."
    echo "Fix: build from this checkout, or set BUILD_DIR to this checkout's build folder."
    echo "ROS 2:    colcon build --cmake-args -DCMAKE_EXPORT_COMPILE_COMMANDS=ON"
    echo "Firmware: cmake -B build -DCMAKE_EXPORT_COMPILE_COMMANDS=ON && cmake --build build"
    echo "To push without this check once: SKIP=clang-tidy git push"
  } >&2
  exit 2
fi

status=0
for db in "${DBS[@]}"; do
  if [[ -n "${RUN_CLANG_TIDY:-}" ]]; then
    "$RUN_CLANG_TIDY" -quiet -clang-tidy-binary "$CLANG_TIDY" -p "$(native_path "$(dirname "$db")")" "${FILTER[@]}" || status=1
  else
    # No parallel runner installed: run clang-tidy file by file (slower, same results).
    if [[ $# -gt 0 ]]; then files=("$@"); else
      mapfile -t files < <(python3 -c "import json,sys;[print(e['file']) for e in json.load(open(sys.argv[1]))]" "$db")
    fi
    for f in "${files[@]}"; do
      [[ "$f" =~ \.(c|cc|cpp|cxx)$ ]] || continue
      [[ "$(realpath "$f")" =~ [\\/](build|install|log|third_party|vendor|Drivers)[\\/] ]] && continue
      "$CLANG_TIDY" --quiet -p "$(dirname "$db")" "$f" || status=1
    done
  fi
done
exit $status
