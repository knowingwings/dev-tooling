## Rust (this repo)

### Checks to run
- `./check` runs every check (hooks, fmt, clippy, test) and prints one line per step, with the failing lines
  and a log path when something fails. Paste its summary into the PR's Evidence section.
- `./check --quick` skips the slow steps while you iterate; run the full `./check` before you say
  you're done. `./check --list` shows exactly what runs.
- Firmware crates: also report `cargo size --release` (text/data/bss) before and after.

### Conventions
- No `unwrap()`. Propagate errors with `?`, or handle them.
- Suppress a lint only with `#[expect(clippy::name, reason = "...")]`, never a bare `#[allow]`.
- Every `unsafe` block needs a `// SAFETY:` comment stating the invariant that makes it sound.
- `cargo run`, `cargo embed` and `probe-rs run` flash the board when a target is set: see Hardware safety.
- Don't edit `clippy.toml`, the `[lints]` tables or `rust-toolchain.toml` to pass a check.
