# Changelog

## Unreleased

**New: GitHub conventions, enforced (from Lauren Tan's evidence-over-diffs approach)**
- Every profile gets an evidence-first PR template (Evidence, Risk / blast radius, suppressions and
  rules learned), issue forms (Task with acceptance criteria and proof expected, Bug, Agent mistake →
  check), CODEOWNERS for the files that define the checks, and a `pr-checks` workflow.
- `check-branch` hook (pre-push): `<type>/<description>` branch names (agent prefixes allowed), no
  direct pushes to `main`.
- `check-pr` (CI): Conventional Commit PR titles, Evidence filled in, exactly one Risk box, and changes
  to the checks not mixed with other code.
- `docs/FEATURE_MAP.md` template: every behaviour and how to verify it, for agents to produce evidence.
- AGENTS.md gains Verification, "When you're corrected", and Git and pull requests sections.
- Trunk-based by default; `develop` can be added in `[git] protected_branches`.

**New: one command, agent roles and auto-merge (more of Lauren Tan's approach)**
- `./check` / `dev-check`: runs every check for the project and prints one line per step, with only
  the failing lines and a log path. Steps live in `[[check.step]]` in `patterns.toml`; `{changed}`
  expands to the files changed on the branch. Pinned to the adopted kit version via `uvx`.
- Agent roles as GitHub Apps you own: architect, builder, reviewer, publisher. Role docs in
  `docs/agents/`, Claude Code subagents in `.claude/agents/` (reviewer and publisher can't edit files).
- `as-agent <role> <command>`: runs git/gh as that role's App (short-lived token, bot identity, pushes
  over HTTPS with the App token) and adds the owner as `Co-authored-by` on every commit.
- `check-pr` requires `Requested-by: @<person>` on PRs opened by a bot.
- `auto-merge` workflow: Low risk + approved by someone else + not changing the checks + no hold label
  → merges when green. Does nothing without branch protection and required checks. Uses the
  publisher App's token when configured.
- `.claude/` and `docs/agents/` count as check changes (CODEOWNERS, mixed-PR rule, never auto-merged).

**Fixes**
- `adopt.sh` exited silently in a repo with no `origin` remote.

## v0.1.0 (2026-11-20)

First version as a repo (previously two zips: dev-tooling, vscode-setup).

**New**
- `scripts/adopt.sh`: adds a profile to a project, never overwrites, pins hooks, writes `.dev-tooling-version`; `--diff` for updates.
- `scripts/install-machine.sh`: CLI tools, extensions, settings symlinked from the repo. Detects
  Code - OSS / VSCodium (Arch) and warns; Windows falls back to a copy when symlinks aren't allowed.
- `check-patterns` and `clang-tidy` are pre-commit hooks served from this repo, so projects no longer copy `tools/`.
- `check-comments` hook (from Lauren Tan's approach): blocks new comments on added lines; allows doc
  comments, `SAFETY:`, `REF(<source>): <fact>`, suppressions with a reason and licence headers.
  Tokenizer-based (strings, raw strings, Rust lifetimes, C++ digit separators), configured per project
  by `[comments]` in `patterns.toml`. The kit's own code follows it.
- Agent instructions moved to `AGENTS.md` (shared `lint/agents/base.md` + a section per stack) so any
  coding agent reads them; `CLAUDE.md` is `@AGENTS.md` plus Claude-only notes.
- `typst` profile: typstyle formatting on commit, and a `typst-compile` hook that builds every entry
  document with the Typst version pinned in `.typst-version` and no system fonts, failing on fonts
  that would render differently on another machine. Tinymist in VS Code with matching settings.
- Self-test: `tests/run_tests.py` (every rule against bad fixtures), `tests/test_adopt.sh`, GitHub Actions CI.

**Fixes found on a work machine**
- `clang_tidy.sh`: Windows / Git Bash support (path filters match `\` and drive letters; MSYS argument rewriting disabled).
- `check_patterns.py`: passes the kit's own Python rules (`git` resolved with `shutil.which`, no `print`, line length).
- `ros_bashrc`: set `ROS_AUTOMATIC_DISCOVERY_RANGE` *before* sourcing ROS. Newer distros default it to SUBNET otherwise.
- `post_build.sh`: relax `set -u` while sourcing colcon's `setup.bash` (it reads unset variables such as `COLCON_TRACE`).
- `install-extensions.sh`: create the profile first. Recent VS Code fails `--install-extension --profile X` with "Profile not found".
- `clang_tidy.sh`: use the runner installed next to the chosen clang-tidy (a runner from another LLVM version fails), fall back to plain clang-tidy.
