#!/usr/bin/env bash
# Checks scripts/adopt.sh for every profile: copies the right files, never overwrites,
# pins the hook rev, writes .robot-kit-version, and --diff reports differences.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fail=0
check() { if eval "$2"; then echo "  ok   $1"; else echo "  FAIL $1"; fail=1; fi; }

for profile in ros2 firmware rust rust-embedded python; do
  echo "== $profile"
  R="$TMP/$profile"; mkdir -p "$R"; git -C "$R" init -q
  echo "# my own notes" > "$R/CLAUDE.md"                 # pre-existing file must survive
  # shellcheck disable=SC2034  # used inside check()'s eval
  out="$("$KIT/scripts/adopt.sh" "$profile" "$R" 2>&1)"

  check "existing CLAUDE.md kept"            '[[ "$(cat "$R/CLAUDE.md")" == "# my own notes" ]]'
  check "skip reported"                      'grep -q "CLAUDE.md" <<< "$(sed -n "/Skipped/,/Git hooks/p" <<< "$out")"'
  check "AGENTS.md has shared base"          'grep -q "^## Comments" "$R/AGENTS.md" && grep -q "^## Hardware safety" "$R/AGENTS.md"'
  check "AGENTS.md has stack section"        'grep -qE "^## (ROS 2|Embedded C/C\+\+ firmware|Rust|Python) \(this repo\)" "$R/AGENTS.md"'
  check "import hint for kept CLAUDE.md"     'grep -q "^  @AGENTS.md" <<< "$out"'
  check ".robot-kit-version written"         'grep -q "^profile=$profile$" "$R/.robot-kit-version"'
  check ".vscode copied"                     '[[ -f "$R/.vscode/settings.json" ]]'
  check "pre-commit config copied"           '[[ -f "$R/.pre-commit-config.yaml" ]]'
  if grep -q "robot-dev-kit" "$R/.pre-commit-config.yaml"; then
    check "hook rev pinned to kit version"   '! grep -q "rev: v0.1.0   # adopt" "$R/.pre-commit-config.yaml" || [[ "$(git -C "$KIT" describe --tags --abbrev=0 2>/dev/null)" == v0.1.0 ]]'
  fi
  check ".gitignore has entries"             '[[ -s "$R/.gitignore" ]]'
  # shellcheck disable=SC2034  # used inside check()'s eval
  out2="$("$KIT/scripts/adopt.sh" "$profile" "$R" 2>&1)"
  check "second run copies nothing"          'grep -q "^Copied (0)" <<< "$out2"'
  check "--diff shows CLAUDE.md difference"  '"$KIT/scripts/adopt.sh" "$profile" "$R" --diff | grep -q "^-# my own notes"'
done

case "$(ls "$TMP/ros2/.devcontainer" 2>/dev/null)" in *Dockerfile*) echo "  ok   ros2 devcontainer copied";; *) echo "  FAIL ros2 devcontainer"; fail=1;; esac
[[ -f "$TMP/firmware/cmake/warnings.cmake" ]] && echo "  ok   firmware warnings.cmake in cmake/" || { echo "  FAIL firmware warnings.cmake"; fail=1; }
grep -q "disallowed-macros" "$TMP/rust-embedded/clippy.toml" && echo "  ok   rust-embedded uses embedded clippy.toml" || { echo "  FAIL rust-embedded clippy.toml"; fail=1; }
echo "== fresh repo gets CLAUDE.md importing AGENTS.md"
F="$TMP/fresh"; mkdir -p "$F"; git -C "$F" init -q
"$KIT/scripts/adopt.sh" firmware "$F" >/dev/null 2>&1
check "CLAUDE.md starts with @AGENTS.md"   '[[ "$(head -1 "$F/CLAUDE.md")" == "@AGENTS.md" ]]'
exit $fail
