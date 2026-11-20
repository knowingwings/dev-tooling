# Changelog

## v0.1.0 (2026-11-20)

First version as a repo (previously two zips: robot-lint-kit, vscode-setup).

**New**
- `scripts/adopt.sh`: adds a profile to a project, never overwrites, pins hooks, writes `.robot-kit-version`; `--diff` for updates.
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
