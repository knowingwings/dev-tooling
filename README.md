# robot-dev-kit

Lint rules, editor config and setup scripts for robotics repos: **ROS 2**, **embedded C/C++**,
**Rust** (host and `no_std`), **Python**, and **Typst** for documents. Every rule's error message says how to fix the problem,
so a human or an agent can act on it without asking. Agent instructions live in `AGENTS.md`, so they
work with any coding agent; `CLAUDE.md` just imports it. The kit tests itself in CI.

## Quick start

```bash
git clone git@github.com:knowingwings/robot-dev-kit.git ~/robot-dev-kit
~/robot-dev-kit/scripts/install-machine.sh                      # once per machine
~/robot-dev-kit/scripts/adopt.sh firmware ~/work/motor-board    # once per project
```

Profiles: `ros2`, `firmware`, `rust`, `rust-embedded`, `python`, `typst`. The full walkthrough, written so an
agent can follow it too, is [docs/SETUP.md](docs/SETUP.md).

## How it stays reproducible

| What | Where it lives | How projects get it |
| --- | --- | --- |
| Shared tools (pattern checker, clang-tidy runner) | `src/`, `lint/shared/` | pre-commit hooks pinned by tag: `rev: v0.1.0` in each project |
| Per-project rules (`patterns.toml`, `.clang-tidy`, `clippy.toml`...) | `lint/<profile>/` | copied once by `adopt.sh`, then owned and edited by the project |
| Agent instructions: `AGENTS.md` (shared base + stack section), `CLAUDE.md` = `@AGENTS.md` | `lint/agents/`, `lint/<profile>/AGENTS.md` | generated once by `adopt.sh`, then owned by the project |
| Editor config (`.vscode/`, ROS 2 dev container) | `vscode/<profile>/` | copied once by `adopt.sh` |
| Your VS Code settings and extensions | `vscode/user/` | `install-machine.sh` symlinks settings, so `git pull` updates every machine |
| Which kit version a project started from | `.robot-kit-version` in the project | written by `adopt.sh` |

**Updating a project to a newer kit:** bump `rev:` in its `.pre-commit-config.yaml`, then run
`adopt.sh <profile> <repo> --diff` to see what changed in the copied files and merge what you want.

## Changing the kit

1. Edit the rule in `lint/<profile>/` (agent instructions: `lint/agents/base.md` for everything, `lint/<profile>/AGENTS.md` for one stack).
2. Add a line that should trigger it to `tests/fixtures/<profile>/`.
3. `python3 tests/run_tests.py --update`, then check `git diff tests/expected/` shows only the change you meant.
4. `bash tests/test_adopt.sh` if you touched `adopt.sh` or the file layout.
5. Commit, push (CI re-runs everything with pinned tool versions), and tag a release: `git tag v0.2.0 && git push --tags`.

## Layout

```
lint/        agents/ ros2/ firmware/ rust/ (+ rust/embedded/) python/ typst/ shared/
vscode/      user/ ros2/ firmware/ rust/ rust-embedded/ python/ typst/
src/         robot_dev_kit/check_patterns.py   (installed by pre-commit as the check-patterns hook)
scripts/     install-machine.sh  adopt.sh
tests/       fixtures/ expected/ run_tests.py test_adopt.sh
docs/        SETUP.md
```

Platforms: Linux (Ubuntu, Arch/Omarchy), macOS, Windows (Git Bash for scripts, WSL2 or Docker for ROS 2).
