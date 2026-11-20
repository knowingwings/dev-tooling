# Setup guide

Do **Phase 1** once per machine, then **Phase 2** once per project with the profile that fits it.
Every step ends in a **Verify** with the expected result. Written so a person or a coding agent can
follow it.

## Rules for an agent following this guide

- Work in one project at a time, on a new branch (`git switch -c dev-env-setup`). Don't commit to
  main or push without being asked.
- Steps marked **STOP (human)** need a person: signing in, choosing hardware settings, anything that
  flashes a board, opens a device port or moves an actuator. Pause and ask.
- Never edit a lint config to make a check pass. Report the failure.
- At the end of each phase, report every Verify command and its result.

To hand a phase to an agent, open the project and say: *"Follow Phase 2 of ~/robot-dev-kit/docs/SETUP.md
for this repo with the firmware profile. Stop at every STOP (human) step."*

## Prerequisites

| Tool | Needed for | Ubuntu | Arch / Omarchy | macOS | Windows |
| --- | --- | --- | --- | --- | --- |
| git, Python 3.10+ | everything | `apt install git python3` | `pacman -S git python` | `brew install git python` | Git for Windows (gives Git Bash) + python.org |
| uv | lint tools | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `pacman -S uv` | `brew install uv` | `winget install astral-sh.uv` |
| VS Code (Microsoft build) | editor | .deb from code.visualstudio.com | `yay -S visual-studio-code-bin` (not the `code` OSS package) | `brew install --cask visual-studio-code` | `winget install Microsoft.VisualStudioCode` |
| Docker | ROS 2 | docs.docker.com | `pacman -S docker docker-buildx`, `systemctl enable --now docker.socket` | Docker Desktop | Docker Desktop (WSL2 backend) |
| Arm GNU toolchain, CMake, Ninja, OpenOCD | C/C++ firmware | `apt install cmake ninja-build openocd` + Arm toolchain | `pacman -S arm-none-eabi-gcc arm-none-eabi-newlib cmake ninja openocd` | `brew install --cask gcc-arm-embedded; brew install cmake ninja open-ocd` | Arm toolchain installer + `winget install Kitware.CMake Ninja-build.Ninja` |
| rustup, probe-rs | Rust | rustup.rs, probe.rs | `pacman -S rustup`, probe-rs from probe.rs | rustup.rs, probe.rs | rustup.rs, probe.rs |
| typst, typstyle | Typst docs | `cargo install typst-cli typstyle --locked` | `pacman -S typst`, `cargo install typstyle --locked` | `brew install typst typstyle` | `winget install Typst.Typst`, `cargo install typstyle --locked` |

On Arch/Omarchy, use the Microsoft VS Code build: the open-source `code` package can't install
Pylance, the C/C++ debugger, Remote-SSH or Dev Containers, and ROS 2 on Arch runs in the dev container.
On Windows, run the scripts from Git Bash; ROS 2 runs in Docker Desktop or WSL2.

## Phase 1: Machine (once per machine)

```bash
git clone git@github.com:knowingwings/robot-dev-kit.git ~/robot-dev-kit
~/robot-dev-kit/scripts/install-machine.sh
```

This installs pre-commit, ruff and clang-tidy (20+) with uv, installs the VS Code extensions into
**ROS2** and **Firmware** profiles, and symlinks `vscode/user/settings.json` into VS Code so that
`git pull` in the kit updates your settings on every machine. Existing settings are backed up next
to the link. On Windows without Developer Mode it copies instead; re-run after each pull.

**STOP (human):**
1. VS Code > gear > Profiles: for ROS2 and Firmware, set *Settings* to "Use Default".
2. Log in to Claude Code (Claude icon in the sidebar).
3. Settings Sync is optional now. If you keep it on, exclude *Settings* so it doesn't fight the link.

Keep `arm-none-eabi-gdb`, `openocd` and `JLinkGDBServerCLExe` on PATH: Cortex-Debug finds them there,
so no machine-specific paths go into the shared settings file.

**Verify:**

| Check | Expected |
| --- | --- |
| `clang-tidy --version` | LLVM 20 or newer, from `~/.local/bin` |
| `pre-commit --version`, `ruff --version` | both print a version |
| `code --profile ROS2 --list-extensions \| wc -l` | 18 or more |
| VS Code settings file | a link to `~/robot-dev-kit/vscode/user/settings.json` (Windows without Developer Mode: a copy) |

## Phase 2: Project (once per project)

```bash
cd <repo> && git switch -c dev-env-setup
~/robot-dev-kit/scripts/adopt.sh <profile> <repo>
```

| Profile | For |
| --- | --- |
| `ros2` | colcon workspaces and ROS 2 packages (C++ and Python) |
| `firmware` | embedded C/C++ with CMake and arm-none-eabi-gcc |
| `rust` | host Rust: tools, services, ROS 2 nodes |
| `rust-embedded` | `no_std` firmware with probe-rs |
| `python` | standalone Python: test rigs, HIL scripts, serial/CAN tools |
| `typst` | Typst documents |

`adopt.sh` copies the profile's files without overwriting anything, builds `AGENTS.md` (shared rules
plus this stack's section) and a `CLAUDE.md` that imports it, pins the kit's hooks to the kit version,
adds `.gitignore` entries, writes `.robot-kit-version` and installs the git hooks. It ends with a
**Still to do** list for that profile: do those steps (details below).

Files it skipped because they already exist: compare with
`adopt.sh <profile> <repo> --diff` and merge by hand. If you kept your own `CLAUDE.md`, make
`@AGENTS.md` its first line.

### ros2

- For a repo of packages cloned into a workspace (`~/ros2_ws/src/<repo>`), add
  `--workspace ~/ros2_ws` so `.vscode/` and `.devcontainer/` go to the workspace root.
- In every `ament_cmake` package, add the warning flags and replace the `BUILD_TESTING` block with
  `lint/ros2/cmake-snippet.cmake`. In `ament_python` packages, delete `test/test_flake8.py` and
  `test/test_pep257.py`.
- Not on Jazzy: change the distro in `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json`
  and `.vscode/settings.json` (Humble uses `python3.10`), and `target-version` in `ruff.toml`.
- **STOP (human):** open the workspace root in VS Code (ROS2 profile) and run *Dev Containers: Reopen
  in Container* (always on Arch; optional on Ubuntu). Then `Ctrl+Shift+B` to build.
- Talking to a real robot: `export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET` (terminals default to
  localhost). From a container, that only works on a Linux host.

**Verify:** new terminal prompt starts `(ros2 jazzy)`; `build/compile_commands.json` exists and `F12`
on an `rclcpp::` symbol works; `colcon test` results unchanged.

### firmware

- `CMakeLists.txt`: `set(CMAKE_EXPORT_COMPILE_COMMANDS ON)`, `include(cmake/warnings.cmake)`,
  `fw_strict_warnings(<your target>)` (never on vendor HAL targets),
  `target_link_options(<target> PRIVATE -Wl,--print-memory-usage)`.
  If `-Werror` breaks the existing build: **STOP (human)** and choose between fixing, applying it to
  clean modules only, or dropping `-Werror` temporarily.
- `patterns.toml`: rename `bsp/`, `drivers/`, `Drivers/` to your layout; non-STM32 MCUs need their
  peripheral names in `fw-register-access-outside-bsp`; delete `fw-no-double` on a double-precision FPU.
- `.clang-tidy`: add the toolchain's include paths to `ExtraArgs`
  (`arm-none-eabi-gcc -xc -E -v /dev/null` lists them).
- **STOP (human):** set the probe, MCU and SVD file in `.vscode/launch.json` and the flash task.
  Motor boards: set the timer debug-freeze bits before debugging with power on (a breakpoint halts
  the CPU, not the PWM).

**Verify:** `cmake --build build` prints FLASH/RAM usage; `main.c` has no clangd errors;
`pre-commit run clang-tidy --hook-stage pre-push --all-files` runs without `stdint.h not found`.

### rust / rust-embedded

- Merge `lint/rust/Cargo-lints.toml` into the workspace `Cargo.toml` and add `[lints] workspace = true`
  to each crate (single crate: rename the headers to `[lints.rust]` / `[lints.clippy]`). HAL crates that
  need `unsafe` get their own `[lints]` table.
- Set `channel` in `rust-toolchain.toml` to your current `rustc --version`, and `edition` in
  `rustfmt.toml` to match your crates.
- `unwrap_used = "deny"` flooding existing code: **STOP (human)**, fix or set it to `"warn"`.
- rust-embedded: set `rust-analyzer.cargo.target`; **STOP (human):** set `chip` and `svdFile` in
  `.vscode/launch.json`; delete `clippy.toml` entries for crates you don't use.

**Verify:** `cargo clippy --workspace --all-targets -- -D warnings` runs and
`cargo clippy 2>&1 | grep -iE "unknown field|does not refer"` prints nothing.

### python

- If `pyproject.toml` was skipped, merge `[dependency-groups]` and the `[tool.*]` sections from
  `lint/python/pyproject.toml`. Then `uv sync`.
- Mark tests that touch a device `@pytest.mark.hardware`; plain `uv run pytest` skips them.

**Verify:** `uv run pyright` runs (hundreds of errors on old code: **STOP (human)**, consider
`typeCheckingMode = "basic"`); `uv run pytest` shows hardware tests deselected.

### typst

- List the documents to build in `.typst-entries` (defaults to `main.typ`).
- Commit the fonts your documents use to `fonts/`. System fonts are ignored on purpose, so a PDF
  looks the same at work and at home; a missing font fails the build with the fix.
- `.typst-version` pins the compiler. Upgrade it in its own commit and check the PDFs.

**Verify:** `pre-commit run typst-compile --hook-stage pre-push --all-files` prints `ok <doc>` for
each document; Tinymist preview opens with `Ctrl+K V`.

## Phase 3: Smoke test (each project)

Add one deliberately bad line, try to commit, and check the commit is blocked with a message that says
how to fix it. Then `git restore --staged <file> && git checkout -- <file>`.

| Profile | Bad line | Expected |
| --- | --- | --- |
| any (C/C++/Rust/Python) | `// tweak gain for the new motor` (`#` in Python) | `no-comments` |
| ros2 (C++ in `src/`) | `auto t = create_wall_timer(1s, []{});` | `ros-no-wall-timer` |
| firmware (app code) | `HAL_Delay(10);` | `fw-no-blocking-delay` |
| rust | `std::thread::sleep(std::time::Duration::from_millis(1));` | clippy `disallowed_methods` (run `cargo clippy`) |
| python | `import os` then `os.system("ls")` | ruff `TID251` |
| typst | `#set text(font: "Arial")` | typst-compile font failure (on push) |

## Updating a project to a newer kit

1. `git -C ~/robot-dev-kit pull`
2. In the project, bump `rev:` for robot-dev-kit in `.pre-commit-config.yaml` to the new tag.
3. `~/robot-dev-kit/scripts/adopt.sh <profile> <repo> --diff` and merge what you want.

## Daily workflow

- Give the agent the task on a branch; it reads `AGENTS.md` (via `CLAUDE.md` for Claude Code).
- In code you're still learning, trace it yourself first (`Shift+Alt+H` call hierarchy, `Shift+F12`
  references), then ask the agent to check your understanding.
- Review the agent's evidence (check output, tests, FLASH/RAM change) before its diff.
- Correct the same mistake twice → make it a check: `CustomFunctions` (clang-tidy),
  `disallowed-methods` (clippy), `banned-api` (ruff), or a `patterns.toml` rule for folder-specific
  rules. Add it to the kit with a fixture (see the README) so every project gets it.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| clang-tidy ignores `CustomFunctions` / unknown `ExcludeHeaderFilterRegex` | clang-tidy older than 20: put `~/.local/bin` first on PATH |
| Firmware clang-tidy: `'stdint.h' file not found` | add the toolchain include paths to `.clang-tidy` |
| `check-comments is not present in repository` | `pre-commit clean`, then retry (cached older kit version) |
| clangd errors everywhere in a ROS workspace | build once (`Ctrl+Shift+B`) to create `build/compile_commands.json` |
| `ros2: command not found` in the Claude panel | use the dev container, or start VS Code with `code .` from a sourced terminal |
| VS Code on Arch can't find Pylance / Dev Containers | you have the OSS build: `yay -S visual-studio-code-bin` |
| Typst: `This repo pins Typst X but you have Y` | install that version, or bump `.typst-version` in its own commit |
| Typst: `uses a font that isn't in fonts/` | commit the font to `fonts/` or use a built-in font |
| OpenOCD `LIBUSB_ERROR_ACCESS` / probe-rs permission denied | install the probe's udev rules, then replug |
