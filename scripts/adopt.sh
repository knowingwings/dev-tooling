#!/usr/bin/env bash
# Add a dev-tooling profile to a project repo.
#
#   scripts/adopt.sh <profile> <repo> [--workspace <dir>] [--diff] [--dry-run]
#
#   profile      ros2 | firmware | rust | rust-embedded | python | typst | astro, or several joined
#                with commas, the main one first (astro,typst): their files are merged
#   repo         the project's git repo root
#   --workspace  ROS 2 only: colcon workspace root for .vscode/ and .devcontainer/ (default: <repo>)
#   --diff       don't copy; show how the repo's copies differ from this kit version (for updating)
#   --dry-run    print what would be copied
#
# Never overwrites a file: anything that already exists is listed so you can merge it by hand
# (use --diff to see the differences). Writes .dev-tooling-version and pins the shared pre-commit
# hooks to this kit's version.
set -euo pipefail

KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
die() { echo "adopt: $*" >&2; exit 1; }

[[ $# -ge 2 ]] || { sed -n '2,15p' "$0"; exit 1; }
PROFILE="$1"; REPO="$(cd "$2" && pwd)"; shift 2
WS="$REPO"; MODE="copy"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --workspace) WS="$(cd "$2" && pwd)"; shift 2 ;;
    --diff) MODE="diff"; shift ;;
    --dry-run) MODE="dry"; shift ;;
    *) die "unknown option $1" ;;
  esac
done
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || die "$REPO is not a git repo"

VERSION="$(git -C "$KIT" describe --tags --always --dirty 2>/dev/null || echo unknown)"
REV="$(git -C "$KIT" describe --tags --abbrev=0 2>/dev/null || git -C "$KIT" rev-parse HEAD)"

# "source|destination" pairs; destinations are relative to $REPO, or start with WS: for the workspace root.
L="$KIT/lint"; V="$KIT/vscode"
GEN="$(mktemp -d)"; trap 'rm -rf "$GEN"' EXIT
make_agents_md() {   # AGENTS.md = shared base + each stack's section
  { cat "$L/agents/base.md"; for s in "$@"; do echo; cat "$L/$s/AGENTS.md"; done; } > "$GEN/AGENTS.md"
}
make_claude_agents() {   # Claude Code subagents: frontmatter + the role's instructions
  mkdir -p "$GEN/claude-agents"
  local role tools desc
  for role in architect builder reviewer publisher; do
    case "$role" in
      architect) tools="Read, Grep, Glob, Bash, Edit, Write"
                 desc="Plans work: turns goals into agent-ready Task issues with acceptance criteria and proof expected, and keeps docs/FEATURE_MAP.md current. Use before building anything non-trivial." ;;
      builder)   tools=""
                 desc="Implements one Task issue per branch and opens a pull request with evidence from ./check and the feature map. Use for code changes." ;;
      reviewer)  tools="Read, Grep, Glob, Bash"
                 desc="Independent review of a pull request: re-runs ./check and the feature-map checks, judges the evidence and the Risk level, then approves or requests changes. Use after a PR is opened." ;;
      publisher) tools="Read, Grep, Glob, Bash"
                 desc="Gets approved work merged safely: follows up stuck PRs, summarises Medium/High risk PRs for the owner, cuts releases, files agent-mistake issues. Use after review." ;;
    esac
    {
      echo "---"; echo "name: $role"; echo "description: $desc"
      [[ -n "$tools" ]] && echo "tools: $tools"
      echo "---"; echo; cat "$L/agents/roles/$role.md"
    } > "$GEN/claude-agents/$role.md"
  done
}
make_claude_agents
AGENT_PAIRS=("$GEN/AGENTS.md|AGENTS.md" "$L/agents/CLAUDE.md|CLAUDE.md"
  "$L/agents/roles|docs/agents" "$GEN/claude-agents|.claude/agents"
  "$L/agents/FEATURE_MAP.md|docs/FEATURE_MAP.md" "$L/github/.github|.github" "$L/shared/check|check" "$L/shared/_typos.toml|_typos.toml")
# One profile's files: sets STACK (its AGENTS.md section), P_PAIRS, P_IGNORE and P_TODO.
# AGENTS in P_PAIRS marks where the shared agent and GitHub files go.
profile_spec() {
case "$1" in
  ros2) STACK=ros2; P_PAIRS=(
      "$L/ros2/.clang-tidy|.clang-tidy" "$L/ros2/.clang-format|.clang-format" "$L/ros2/ruff.toml|ruff.toml"
      "$L/ros2/patterns.toml|patterns.toml" "$L/ros2/.pre-commit-config.yaml|.pre-commit-config.yaml"
      AGENTS "$V/ros2/.vscode|WS:.vscode" "$V/ros2/.devcontainer|WS:.devcontainer")
    P_IGNORE=(build/ install/ log/ .vscode/ros.env .cache/)
    P_TODO="Add cmake-snippet.cmake ($L/ros2/cmake-snippet.cmake) to each ament_cmake package (SETUP.md Phase 2.4).
Delete test/test_flake8.py and test/test_pep257.py from ament_python packages.
Not on Jazzy? Change the distro in .devcontainer/ and .vscode/settings.json (SETUP.md Phase 2.3)." ;;
  firmware) STACK=firmware; P_PAIRS=(
      "$L/firmware/.clang-tidy|.clang-tidy" "$L/firmware/.clang-format|.clang-format" "$L/firmware/.clangd|.clangd"
      "$L/firmware/patterns.toml|patterns.toml" "$L/firmware/.pre-commit-config.yaml|.pre-commit-config.yaml"
      AGENTS "$L/firmware/warnings.cmake|cmake/warnings.cmake" "$V/firmware/.vscode|.vscode")
    P_IGNORE=(build/ build-host/)
    P_TODO="Wire cmake/warnings.cmake into CMakeLists.txt (SETUP.md Phase 3.3).
Rename the folders in patterns.toml to your layout (3.2).
Add the arm-none-eabi include paths to .clang-tidy (3.4).
HUMAN: set MCU, probe and SVD in .vscode/launch.json and tasks.json (3.5)." ;;
  rust|rust-embedded)
    STACK=rust
    CLIPPY="$L/rust/clippy.toml"; VS="$V/rust/.vscode"
    [[ "$1" == rust-embedded ]] && { CLIPPY="$L/rust/embedded/clippy.toml"; VS="$V/rust-embedded/.vscode"; }
    P_PAIRS=(
      "$CLIPPY|clippy.toml" "$L/rust/rustfmt.toml|rustfmt.toml" "$L/rust/rust-toolchain.toml|rust-toolchain.toml"
      "$L/rust/patterns.toml|patterns.toml" "$L/rust/.pre-commit-config.yaml|.pre-commit-config.yaml"
      AGENTS "$VS|.vscode")
    P_IGNORE=(target/)
    P_TODO="Merge $L/rust/Cargo-lints.toml into Cargo.toml, and add [lints] workspace = true to each crate (SETUP.md Phase 4.3).
Set channel in rust-toolchain.toml to your current rustc version, and edition in rustfmt.toml to match your crates (4.2, 4.3)."
    [[ "$1" == rust-embedded ]] && P_TODO+="
Set rust-analyzer.cargo.target in .vscode/settings.json; HUMAN: set chip and SVD in .vscode/launch.json (4.4)." ;;
  python) STACK=python; P_PAIRS=(
      "$L/python/.pre-commit-config.yaml|.pre-commit-config.yaml" AGENTS
      "$L/python/patterns.toml|patterns.toml"
      "$L/python/pyproject.toml|pyproject.toml" "$V/python/.vscode|.vscode")
    P_IGNORE=(.venv/)
    P_TODO="If pyproject.toml was skipped, merge [dependency-groups] and the [tool.*] sections from $L/python/pyproject.toml (SETUP.md Phase 5.2).
Mark tests that need a device with @pytest.mark.hardware (5.3).
Run: uv sync" ;;
  typst) STACK=typst; P_PAIRS=(
      "$L/typst/.pre-commit-config.yaml|.pre-commit-config.yaml" AGENTS
      "$L/typst/.typst-version|.typst-version" "$L/typst/.typst-entries|.typst-entries" "$V/typst/.vscode|.vscode"
      "$L/typst/patterns.toml|patterns.toml")
    P_IGNORE=(build/)
    P_TODO="List your entry documents in .typst-entries (it defaults to main.typ).
Commit the fonts your documents use to fonts/ (system fonts are ignored so PDFs match on every machine).
Install typst $(cat "$L/typst/.typst-version") and typstyle if missing (SETUP.md, Typst)." ;;
  astro) STACK=astro; P_PAIRS=(
      "$L/astro/.pre-commit-config.yaml|.pre-commit-config.yaml" AGENTS
      "$L/astro/patterns.toml|patterns.toml" "$L/astro/eslint.config.mjs|eslint.config.mjs"
      "$L/astro/.prettierrc.json|.prettierrc.json" "$L/astro/.prettierignore|.prettierignore"
      "$V/astro/.vscode|.vscode")
    P_IGNORE=(dist/ .astro/ node_modules/)
    P_TODO="Install the tools the checks use, as dev dependencies (SETUP.md, astro): npm install --save-dev @astrojs/check typescript@~6.0 eslint@^10 @eslint/js@^10 typescript-eslint eslint-plugin-astro eslint-plugin-jsx-a11y-x prettier prettier-plugin-astro
Commit package.json and package-lock.json. On each machine, run npm ci before the hooks." ;;
  *) die "unknown profile '$1' (ros2, firmware, rust, rust-embedded, python, typst, astro)" ;;
esac
return 0
}

dest_path() { local d="$1"; [[ "$d" == WS:* ]] && echo "$WS/${d#WS:}" || echo "$REPO/$d"; }

# Every file a pair covers, as "source-file|destination-file".
expand() {
  local src="$1" dst="$2"
  if [[ -d "$src" ]]; then
    (cd "$src" && find . -type f | sed 's|^\./||' | sort) | while read -r f; do echo "$src/$f|$dst/$f"; done
  else
    echo "$src|$dst"
  fi
}

# Stage every profile's files in $STAGE, merging a file that two profiles both provide
# (src/dev_tooling/merge_profiles.py). The copy, --diff and --dry-run steps below then use $STAGE.
IFS=',' read -r -a PROFILES <<< "$PROFILE"
[[ ${#PROFILES[@]} -ge 1 ]] || die "no profile given"
STACKS=(); ALL=(); IGNORE=(); TODO=""
for p in "${PROFILES[@]}"; do
  profile_spec "$p"
  [[ " ${STACKS[*]} " == *" $STACK "* ]] || STACKS+=("$STACK")
  ALL+=("@profile:$p" "${P_PAIRS[@]}"); IGNORE+=("${P_IGNORE[@]}")
  if [[ ${#PROFILES[@]} -eq 1 ]]; then TODO="$P_TODO"; else
    while IFS= read -r line; do TODO+="${TODO:+$'\n'}[$p] $line"; done <<< "$P_TODO"
  fi
done
make_agents_md "${STACKS[@]}"

STAGE="$GEN/stage"; STAGED=(); kept=(); PY=""
find_python() {
  local c
  for c in python3 python py; do
    command -v "$c" >/dev/null && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))' 2>/dev/null \
      && { PY="$c"; return; }
  done
  die "combining profiles needs Python 3.10 or newer to merge $1"
}
stage_file() {   # stage_file <source file> <destination> <profile>
  local key="${2/#WS:/@ws/}"
  local t="$STAGE/$key" rc=0
  if [[ ! -e "$t" ]]; then mkdir -p "$(dirname "$t")"; cp -p "$1" "$t"; STAGED+=("$key"); return; fi
  cmp -s "$1" "$t" && return
  [[ -n "$PY" ]] || find_python "$2"
  PYTHONPATH="$KIT/src" "$PY" -m dev_tooling.merge_profiles "$2" "$t" "$1" || rc=$?
  case "$rc" in
    0) ;;
    3) kept+=("${2#WS:} (kept the first profile's; $3's differs)") ;;
    *) die "couldn't merge $3's $2" ;;
  esac
}
agents_staged=""
for item in "${ALL[@]}"; do
  case "$item" in
    @profile:*) p="${item#@profile:}"; continue ;;
    AGENTS) [[ -n "$agents_staged" ]] && continue; agents_staged=1; pairs=("${AGENT_PAIRS[@]}") ;;
    *) pairs=("$item") ;;
  esac
  for pair in "${pairs[@]}"; do
    while IFS='|' read -r s d; do stage_file "$s" "$d" "$p"; done < <(expand "${pair%%|*}" "${pair#*|}")
  done
done
PAIRS=()
for key in "${STAGED[@]}"; do PAIRS+=("$STAGE/$key|${key/#@ws\//WS:}"); done

copied=(); skipped=()
for pair in "${PAIRS[@]}"; do
  src="${pair%%|*}"; dst="$(dest_path "${pair#*|}")"
  while IFS='|' read -r s d; do
    rel="${d#"$REPO"/}"; [[ "$d" == "$WS"/* && "$WS" != "$REPO" ]] && rel="(workspace) ${d#"$WS"/}"
    case "$MODE" in
      diff)
        if [[ -f "$d" ]]; then
          diff -u --label "repo: $rel" --label "kit $VERSION" "$d" "$s" || true
        else
          echo "missing in repo: $rel"
        fi ;;
      dry) [[ -e "$d" ]] && echo "skip (exists): $rel" || echo "copy: $rel" ;;
      copy)
        if [[ -e "$d" ]]; then skipped+=("$rel"); else
          mkdir -p "$(dirname "$d")"; cp -p "$s" "$d"; copied+=("$rel")
        fi ;;
    esac
  done < <(expand "$src" "$dst")
done

[[ "$MODE" != copy ]] && exit 0

# Pin the kit version wherever a copied file says "adopt.sh sets this" (hooks, pr-checks workflow).
for rel in "${copied[@]}"; do
  f="$REPO/$rel"
  [[ -f "$f" ]] && grep -q "adopt.sh sets this" "$f" || continue
  sed -i.bak "/adopt.sh sets this/ s/v0\.1\.0/${REV}/" "$f" && rm -f "$f.bak"
done

# CODEOWNERS: fill in the GitHub owner from the origin remote.
owner="$(git -C "$REPO" remote get-url origin 2>/dev/null | sed -nE 's#.*github\.com[:/]+([^/]+)/.*#\1#p' || true)"
if printf '%s\n' "${copied[@]}" | grep -qx '.github/CODEOWNERS'; then
  if [[ -n "$owner" ]]; then
    sed -i.bak "s/@OWNER/@${owner}/" "$REPO/.github/CODEOWNERS" && rm -f "$REPO/.github/CODEOWNERS.bak"
  else
    TODO+="
Replace @OWNER in .github/CODEOWNERS with your GitHub username (no GitHub origin remote found)."
  fi
fi

# .gitignore entries
touch "$REPO/.gitignore"
for g in "${IGNORE[@]}" .dev-check/; do grep -qxF "$g" "$REPO/.gitignore" || echo "$g" >> "$REPO/.gitignore"; done

for rel in "${copied[@]}"; do
  [[ "$rel" != "(workspace) "* && -f "$REPO/$rel" ]] || continue
  [[ "$(head -c2 "$REPO/$rel")" == '#!' || "$rel" == *bashrc ]] || continue
  attr="/$rel text eol=lf"
  grep -qxF "$attr" "$REPO/.gitattributes" 2>/dev/null || echo "$attr" >> "$REPO/.gitattributes"
done

printf 'profile=%s\nkit_version=%s\nadopted=%s\n' "$PROFILE" "$VERSION" "$(date +%F)" > "$REPO/.dev-tooling-version"

if command -v pre-commit >/dev/null && [[ -f "$REPO/.pre-commit-config.yaml" ]]; then
  (cd "$REPO" && pre-commit install >/dev/null && pre-commit install --hook-type pre-push >/dev/null) \
    && hooks="installed" || hooks="FAILED (run: pre-commit install && pre-commit install --hook-type pre-push)"
else
  hooks="not installed (pre-commit missing: uv tool install pre-commit)"
fi

echo "dev-tooling $VERSION, profile $PROFILE -> $REPO"
echo
echo "Copied (${#copied[@]}):"; printf '  %s\n' "${copied[@]:-none}"
if [[ ${#skipped[@]} -gt 0 ]]; then
  echo "Skipped, already exist (${#skipped[@]}): merge by hand; see differences with --diff"
  printf '  %s\n' "${skipped[@]}"
fi
if [[ ${#kept[@]} -gt 0 ]]; then
  echo "Not merged, two profiles provide it (${#kept[@]}): compare with --diff for each profile"
  printf '  %s\n' "${kept[@]}"
fi
echo "Git hooks: $hooks"
if [[ -f "$REPO/CLAUDE.md" ]] && ! grep -q '^@AGENTS.md' "$REPO/CLAUDE.md"; then
  echo
  echo "Your existing CLAUDE.md was kept. Add this as its first line so Claude Code reads AGENTS.md:"
  echo "  @AGENTS.md"
fi
echo
echo "On GitHub (human, once per repo): Settings > Branches > add a rule for main:"
echo "  require a pull request, require the pr-checks and CI status checks, require review from Code Owners."
echo
echo "Still to do:"
while IFS= read -r line; do echo "  - $line"; done <<< "$TODO"
