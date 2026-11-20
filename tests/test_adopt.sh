#!/usr/bin/env bash
# Checks scripts/adopt.sh for every profile: copies the right files, never overwrites,
# pins the hook rev, writes .dev-tooling-version, and --diff reports differences.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
fail=0
# shellcheck disable=SC2034  # used inside check()'s eval
EXPECTED_REV="$(git -C "$KIT" describe --tags --abbrev=0 2>/dev/null || git -C "$KIT" rev-parse HEAD)"
check() { if eval "$2"; then echo "  ok   $1"; else echo "  FAIL $1"; fail=1; fi; }

for profile in ros2 firmware rust rust-embedded python typst astro; do
  echo "== $profile"
  R="$TMP/$profile"; mkdir -p "$R"; git -C "$R" init -q
  git -C "$R" remote add origin git@github.com:someone/$profile-repo.git
  echo "# my own notes" > "$R/CLAUDE.md"                 # pre-existing file must survive
  # shellcheck disable=SC2034  # used inside check()'s eval
  out="$("$KIT/scripts/adopt.sh" "$profile" "$R" 2>&1)"

  check "existing CLAUDE.md kept"            '[[ "$(cat "$R/CLAUDE.md")" == "# my own notes" ]]'
  check "skip reported"                      'grep -q "CLAUDE.md" <<< "$(sed -n "/Skipped/,/Git hooks/p" <<< "$out")"'
  check "AGENTS.md has shared base"          'grep -q "^## Comments" "$R/AGENTS.md" && grep -q "^## Hardware safety" "$R/AGENTS.md"'
  check "AGENTS.md has stack section"        'grep -qE "^## (ROS 2|Embedded C/C\+\+ firmware|Rust|Python|Typst documents|Astro site) \(this repo\)" "$R/AGENTS.md"'
  check "import hint for kept CLAUDE.md"     'grep -q "^  @AGENTS.md" <<< "$out"'
  check ".dev-tooling-version written"         'grep -q "^profile=$profile$" "$R/.dev-tooling-version"'
  check ".vscode copied"                     '[[ -f "$R/.vscode/settings.json" ]]'
  check "pre-commit config copied"           '[[ -f "$R/.pre-commit-config.yaml" ]]'
  if grep -q "dev-tooling" "$R/.pre-commit-config.yaml"; then
    check "hook rev pinned to kit version"   '! grep -q "rev: v0.1.0   # adopt" "$R/.pre-commit-config.yaml" || [[ "$(git -C "$KIT" describe --tags --abbrev=0 2>/dev/null)" == v0.1.0 ]]'
  fi
  check "PR template copied"                 '[[ -f "$R/.github/pull_request_template.md" ]]'
  check "issue templates copied"             '[[ -f "$R/.github/ISSUE_TEMPLATE/agent-mistake.yml" && -f "$R/.github/ISSUE_TEMPLATE/task.yml" ]]'
  check "CODEOWNERS owner filled in"         'grep -q "^/AGENTS.md *@someone$" "$R/.github/CODEOWNERS"'
  check "pr-checks pinned to kit version"    'grep -q "KIT_REV: $EXPECTED_REV " "$R/.github/workflows/pr-checks.yml"'
  check "feature map copied"                 '[[ -f "$R/docs/FEATURE_MAP.md" ]]'
  check "role docs copied"                   '[[ -f "$R/docs/agents/reviewer.md" && -f "$R/docs/agents/builder.md" ]]'
  check "Claude subagents generated"         'head -2 "$R/.claude/agents/reviewer.md" | grep -qx "name: reviewer"'
  check "reviewer can't edit files"          'grep -qx "tools: Read, Grep, Glob, Bash" "$R/.claude/agents/reviewer.md"'
  check "./check wrapper pinned"             'grep -q "rev=\"$EXPECTED_REV\"" "$R/check" && [[ -x "$R/check" ]]'
  check ".dev-check/ ignored"                'grep -qx ".dev-check/" "$R/.gitignore"'
  check ".gitignore has entries"             '[[ -s "$R/.gitignore" ]]'
  check "_typos.toml copied (British spelling)" 'grep -qx "locale = \"en-gb\"" "$R/_typos.toml"'
  check "prose, secrets and typos hooks on"   'grep -q "id: check-prose" "$R/.pre-commit-config.yaml" && grep -q "id: check-secrets" "$R/.pre-commit-config.yaml" && grep -q "id: typos" "$R/.pre-commit-config.yaml"'
  check "AGENTS.md has writing and secrets"  'grep -q "^## Writing" "$R/AGENTS.md" && grep -q "^## Secrets" "$R/AGENTS.md"'
  # shellcheck disable=SC2034  # used inside check()'s eval
  out2="$("$KIT/scripts/adopt.sh" "$profile" "$R" 2>&1)"
  check "second run copies nothing"          'grep -q "^Copied (0)" <<< "$out2"'
  check "--diff shows CLAUDE.md difference"  '"$KIT/scripts/adopt.sh" "$profile" "$R" --diff | grep -q "^-# my own notes"'
done

case "$(ls "$TMP/ros2/.devcontainer" 2>/dev/null)" in *Dockerfile*) echo "  ok   ros2 devcontainer copied";; *) echo "  FAIL ros2 devcontainer"; fail=1;; esac
[[ -f "$TMP/firmware/cmake/warnings.cmake" ]] && echo "  ok   firmware warnings.cmake in cmake/" || { echo "  FAIL firmware warnings.cmake"; fail=1; }
grep -q "disallowed-macros" "$TMP/rust-embedded/clippy.toml" && echo "  ok   rust-embedded uses embedded clippy.toml" || { echo "  FAIL rust-embedded clippy.toml"; fail=1; }
[[ -f "$TMP/astro/eslint.config.mjs" && -f "$TMP/astro/.prettierrc.json" ]] && echo "  ok   astro ESLint and Prettier configs copied" || { echo "  FAIL astro configs"; fail=1; }
grep -qx "node_modules/" "$TMP/astro/.gitignore" && echo "  ok   astro ignores node_modules/" || { echo "  FAIL astro .gitignore"; fail=1; }
# shellcheck disable=SC2034  # used inside check()'s eval
PC="$TMP/python/.pre-commit-config.yaml"
check "python ruff hooks use the project's ruff"  'grep -q "entry: uv run ruff check --fix" "$PC" && ! grep -q "ruff-pre-commit" "$PC"'
check "python pyright hook checks staged files"   '! sed -n "/id: pyright/,/^$/p" "$PC" | grep -q "pass_filenames"'
echo "== fresh repo gets CLAUDE.md importing AGENTS.md"
F="$TMP/fresh"; mkdir -p "$F"; git -C "$F" init -q
"$KIT/scripts/adopt.sh" firmware "$F" >/dev/null 2>&1
check "CLAUDE.md starts with @AGENTS.md"   '[[ "$(head -1 "$F/CLAUDE.md")" == "@AGENTS.md" ]]'
echo "== typst-compile with no entry documents needs no typst"
mkdir -p "$TMP/fakebin"; printf '#!/bin/sh\nexit 99\n' > "$TMP/fakebin/typst"; chmod +x "$TMP/fakebin/typst"
printf '# no documents yet\n' > "$TMP/typst/.typst-entries"
check "exits 0 before it calls typst"       '(cd "$TMP/typst" && PATH="$TMP/fakebin:$PATH" bash "$KIT/lint/shared/typst_compile.sh" | grep -q "no entry documents")'
exit $fail
