# VS Code setup: ROS 2, firmware (C/C++ and Rust), Python: same at work and home

Three layers, each synced a different way:

| Layer | What | How it stays the same everywhere |
|---|---|---|
| **You** | editor behaviour, extensions, profiles | Settings Sync (built in) |
| **Each repo** | `.vscode/` tasks, debug configs, clangd/ROS settings | committed to git |
| **Toolchain** | ROS distro, compilers, lint tools | ROS 2: dev container. Rust: `rust-toolchain.toml`. Python: `uv.lock`. Firmware: native install (USB debug probes and containers don't mix well) |

## 1. Once per machine (about 10 minutes)

1. Install VS Code, then sign in to **Settings Sync** (gear icon > Backup and Sync Settings) with
   GitHub or Microsoft, and include Profiles. If your work machine blocks that, keep `user/` in a
   personal dotfiles repo instead.
2. `bash user/install-extensions.sh`. This creates two **profiles**, `ROS2` and `Firmware`, each with only
   the extensions it needs. Switch with the gear icon > Profiles, or pick one per folder.
   In the Profiles editor, set each profile's *Settings* to "Use Default" so they share one settings file.
3. Paste `user/settings.json` into *Preferences: Open User Settings (JSON)*.
4. Machine-specific paths go in user settings (they differ between work and home), e.g.
   ```jsonc
   "cortex-debug.armToolchainPath": "/opt/arm-gnu-toolchain/bin",
   "cortex-debug.openocdPath": "/usr/bin/openocd",
   "cortex-debug.JLinkGDBServerPath": "/opt/SEGGER/JLink/JLinkGDBServerCLExe"
   ```

## 2. Once per repo

**ROS 2 workspace** (open the folder that contains `src/`):
- Copy `ros2/.vscode/` and `ros2/.devcontainer/` in, add the `.gitignore` lines, and commit.
- Either *Dev Containers: Reopen in Container* (recommended: identical at work and home) or
  run natively on Ubuntu with ROS installed.
- `Ctrl+Shift+B` builds. It also merges colcon's per-package `compile_commands.json` so clangd
  understands every package, and writes `ros.env` for the gdb debug config.
- New terminals source ROS and your workspace automatically. That includes the terminal you run
  `claude` in, so the agent can use `ros2`/`colcon` without being told to source anything.

**Firmware repo:**
- Copy `firmware/.vscode/` in. Edit `launch.json` for your MCU (OpenOCD target cfg, J-Link device, SVD file)
  and the flash task's target.
- The SVD file gives you a live peripheral register view while debugging. Get it from the vendor pack.

`scripts/adopt.sh` adds the lint profile alongside the `.vscode/` folder. The lint tasks run its hooks,
and their errors appear in the Problems panel (`Ctrl+Shift+M`) and inline via Error Lens.

**Rust repo:** copy `rust/.vscode/` (host) or `rust-embedded/.vscode/` (no_std firmware).
- rust-analyzer runs clippy on save, so the lint kit's `clippy.toml` errors show inline as you type.
- Host: `F5` debugs through CodeLLDB, which builds with cargo first. There's also a "Debug" lens above `main()` and every test.
- Embedded: set `rust-analyzer.cargo.target` and the probe-rs `chip`. probe-rs flashes and debugs over
  ST-Link, J-Link or CMSIS-DAP with no OpenOCD config, and shows RTT/defmt logs in the debug console.
- Use the **Firmware** profile for embedded Rust (it has probe-rs). Host Rust works in either profile.

**Python project:** copy `python/.vscode/` and the lint kit's `python/pyproject.toml`, then `uv sync`.
- The Testing sidebar runs pytest, and hardware tests are deselected unless you run the "HARDWARE tests" task.
- The interpreter is the project's `.venv` automatically, so there's no "select interpreter" dance.

## 3. Using Claude Code in this setup

- The **extension** (sidebar panel, inline diffs) is best for reviewing changes. Run `claude`
  in the integrated terminal when you want the CLI. Both read the repo's `CLAUDE.md`, which imports
  `AGENTS.md` (the instructions every agent shares).
- If the extension panel can't see `ros2`/`colcon`, it inherited VS Code's environment rather than a
  sourced shell. Use the dev container (environment baked in) or launch VS Code with `code .` from a sourced terminal.
- Review agent diffs in the side-by-side diff view. `diffEditor.hideUnchangedRegions` collapses
  the noise so you read only what changed.

## 4. Getting familiar with a codebase (the habits from earlier)

clangd gives you real navigation across ROS packages and firmware:
- `F12` go to definition, `Shift+F12` find all references
- `Shift+Alt+H` **call hierarchy**: who calls this, and what does it call. This is the fastest way to trace a code path.
- `Ctrl+T` jump to any symbol in the workspace
- Hover for types; inlay hints show parameter names and deduced types inline

When you're learning a new area, trace it yourself with these first, then ask Claude to check your understanding.

## Gotchas

- **Cursor:** the ROS extension is on Open VSX now, so this setup works there too if you ever switch back.
- **Remote SSH to a robot:** `ms-vscode-remote.remote-ssh` lets you edit and attach gdb on the robot itself.
  Install clangd there too for navigation.
- **Debugging motor boards:** a breakpoint halts the CPU but not the timers. See the warning at the top of
  `firmware/.vscode/launch.json` before debugging with motor power on.
