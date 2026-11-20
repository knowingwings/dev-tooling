# dev-tooling

Lint rules, editor config, agent instructions and setup scripts for **ROS 2**, **embedded C/C++**,
**Rust** (host and `no_std`), **Python**, and **Typst** for documents. Every rule's error message says
how to fix the problem, so a human or an agent can act on it without asking. Agent instructions live in `AGENTS.md`, so they
work with any coding agent; `CLAUDE.md` just imports it. The kit tests itself in CI.

## Quick start

```bash
git clone git@github.com:knowingwings/dev-tooling.git ~/dev-tooling
~/dev-tooling/scripts/install-machine.sh                      # once per machine
~/dev-tooling/scripts/adopt.sh firmware ~/work/motor-board    # once per project
```

Profiles: `ros2`, `firmware`, `rust`, `rust-embedded`, `python`, `typst`. The full walkthrough, written so an
agent can follow it too, is [docs/SETUP.md](docs/SETUP.md).

## How it stays reproducible

| What | Where it lives | How projects get it |
| --- | --- | --- |
| Shared tools (pattern checker, clang-tidy runner) | `src/`, `lint/shared/` | pre-commit hooks pinned by tag: `rev: v0.1.0` in each project |
| Per-project rules (`patterns.toml`, `.clang-tidy`, `clippy.toml`...) | `lint/<profile>/` | copied once by `adopt.sh`, then owned and edited by the project |
| Agent instructions: `AGENTS.md` (shared base + stack section), `CLAUDE.md` = `@AGENTS.md` | `lint/agents/`, `lint/<profile>/AGENTS.md` | generated once by `adopt.sh`, then owned by the project |
| GitHub conventions: PR and issue templates, CODEOWNERS, `pr-checks` workflow, feature map | `lint/github/`, `lint/agents/FEATURE_MAP.md` | copied once by `adopt.sh` for every profile |
| Editor config (`.vscode/`, ROS 2 dev container) | `vscode/<profile>/` | copied once by `adopt.sh` |
| Your VS Code settings and extensions | `vscode/user/` | `install-machine.sh` symlinks settings, so `git pull` updates every machine |
| Which kit version a project started from | `.dev-tooling-version` in the project | written by `adopt.sh` |

**Updating a project to a newer kit:** bump `rev:` in its `.pre-commit-config.yaml`, then run
`adopt.sh <profile> <repo> --diff` to see what changed in the copied files and merge what you want.

## Working on the kit

The kit follows its own conventions: branch `<type>/<description>`, Conventional Commit PR titles,
an Evidence section in every PR. CI checks all of it.

## Changing the kit

1. Edit the rule in `lint/<profile>/` (agent instructions: `lint/agents/base.md` for everything, `lint/<profile>/AGENTS.md` for one stack).
2. Add a line that should trigger it to `tests/fixtures/<profile>/`.
3. `python3 tests/run_tests.py --update`, then check `git diff tests/expected/` shows only the change you meant.
4. `bash tests/test_adopt.sh` if you touched `adopt.sh` or the file layout.
5. Commit, push (CI re-runs everything with pinned tool versions), and tag a release: `git tag v0.2.0 && git push --tags`.

## Layout

```
lint/        agents/ github/ ros2/ firmware/ rust/ (+ rust/embedded/) python/ typst/ shared/
vscode/      user/ ros2/ firmware/ rust/ rust-embedded/ python/ typst/
src/         dev_tooling/  check_patterns, check_comments, check_git (the hooks and CI checks)
scripts/     install-machine.sh  adopt.sh
tests/       fixtures/ expected/ run_tests.py test_adopt.sh
docs/        SETUP.md
```

Platforms: Linux (Ubuntu, Arch/Omarchy), macOS, Windows (Git Bash for scripts, WSL2 or Docker for ROS 2).
