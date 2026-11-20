# Robot lint kit: ROS 2, embedded C/C++, Rust, Python

Profiles: `ros2/`, `firmware/` (C/C++), `rust/` (host + `rust/embedded/`), `python/` (standalone projects).
All of them follow the same idea and share `shared/check_patterns.py`.

## Rust (`rust/`)
- `Cargo-lints.toml`: workspace `[lints]`. No `unwrap`, no unchecked numeric casts (Rust's `-Wconversion`),
  `unsafe` denied outside HAL crates, and every suppression must be `#[expect(lint, reason = "...")]`.
- `clippy.toml` / `embedded/clippy.toml`: banned functions and types, with the fix as the reason
  (`thread::sleep`, `SystemTime::now`, `process::exit`, blocking HAL delays, `panic!` in firmware...).
- `rust-toolchain.toml` pins the compiler so work, home and CI agree. `rustfmt.toml` uses stable options only.
- Embedded tip: keep control logic in a `no_std` crate with **no HAL dependency**, so `cargo test` runs it on
  your laptop. That's the Rust equivalent of the firmware register-access rule.

## Python (`python/`)
For test rigs, HIL scripts, serial/CAN tools and analysis (ROS 2 Python packages use `ros2/ruff.toml`).
- uv for environments, ruff for lint and format, **pyright** for types (the same engine as Pylance, so the editor and
  pre-commit agree). Astral's `ty` is faster but still in beta, so it's worth trying later.
- pytest with a `hardware` marker that is **deselected by default**: `pytest` (what an agent runs) never
  touches a device, and `pytest -m hardware` runs the hardware tests when you mean it.

---

# ROS 2 + embedded C/C++ profiles

A starting point for the "make the codebase enforce quality" approach: every rule has an
error message that says how to fix the problem, so an agent (or a new teammate) can act on it
without asking. Works the same in VS Code, Cursor, the terminal and CI.

## What's in it

| Layer | ROS 2 repos | Firmware repos |
|---|---|---|
| Compiler warnings as errors | `ros2/cmake-snippet.cmake` | `firmware/warnings.cmake` |
| Formatting | `.clang-format`, ruff format | `.clang-format` |
| Static analysis + banned functions | `.clang-tidy`, `ruff.toml` (banned-api) | `.clang-tidy` |
| Where-in-the-tree rules | `patterns.toml` | `patterns.toml` |
| Wiring | `.pre-commit-config.yaml` | `.pre-commit-config.yaml` |
| Agent instructions (kept short) | `CLAUDE.md` | `CLAUDE.md` + `.clangd` |

`shared/` holds `check_patterns.py` (the path-scoped rule checker) and the `clang-tidy` hook
(runs clang-tidy over every `compile_commands.json` colcon or CMake produced).

**How the work is split:**
- clang-tidy and ruff ban *functions* (malloc, sleep_for, time.sleep...). They use the AST, so there are no false hits in comments or strings.
- `patterns.toml` covers *where* rules: "register access only in bsp/", "no HAL_Delay outside init", "spin only in main()".
- Compiler flags catch the rest: implicit conversions, double promotion, stack usage.

## Setup (per repo)

```bash
~/robot-dev-kit/scripts/adopt.sh ros2 ~/work/my_repo     # or firmware, rust, rust-embedded, python
```

`adopt.sh` copies the profile's per-project files (never overwriting), pins the shared hooks to this kit's
version and installs the git hooks. See `docs/SETUP.md` for the full walkthrough. The manual steps below
are what it prints at the end.

- **ROS 2:** add `cmake-snippet.cmake` to each package and set the `~/.colcon/defaults.yaml` shown in it.
  Delete the `test_flake8.py` / `test_pep257.py` files from ament_python packages, since ruff replaces them.
- **Firmware:** `include(cmake/warnings.cmake)` and call `fw_strict_warnings(app)` on your own targets.
  Add your arm-none-eabi include paths to `.clang-tidy` (the command is in the file).
  Rename `bsp/`, `drivers/`, `Drivers/` in `patterns.toml` to match your layout.

## Adopting it on an existing repo

Don't fix everything at once. pre-commit only checks staged files, and the clang-tidy hook only
checks changed files on push, so quality ratchets up as you touch code. If a rule floods a module,
disable it in a sub-directory `.clang-tidy` with `InheritParentConfig: true` and come back to it later.

## Growing it (this is the point)

Whenever you correct an agent for the same thing twice, add a check instead of a CLAUDE.md line:
1. Is it a function that should never be called? Add it to `CustomFunctions` (clang-tidy) or `banned-api` (ruff).
2. Is it only wrong in certain directories? Add a rule to `patterns.toml`.
3. Is it a type or units mistake? Change the API so the mistake can't compile (strong types, enums, `std::chrono`).

Write the message as the fix. Test a new rule by committing a bad example and checking it fails.

## Next layer: verification (so agents can check their own work)

- **ROS 2:** `launch_testing` integration tests, plus replaying a recorded rosbag through the node
  and asserting on outputs. Run everything with `use_sim_time`.
- **Firmware:** host-side unit tests (GoogleTest or Unity) for app logic. The register-access rule is
  what makes this possible, because app code only talks to driver interfaces you can fake. Renode can emulate
  many STM32/nRF boards, so an agent can run the actual firmware without hardware.
- **Formal checks:** CBMC (bounded model checking for C) suits small, critical state machines and
  parsers if you want to go further.

## Suppressions

`// lint-allow(<rule-id>): <reason>` on the same or previous line. A missing or one-word reason
is itself an error. Grep for `lint-allow` in review to see every exception in one place.
