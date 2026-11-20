# Working in this repo

## Before you say a change is done
Run these and include a short summary of the output in your final message:

1. `cargo fmt --all`
2. `cargo clippy --workspace --all-targets -- -D warnings`
3. `cargo test --workspace`
4. Firmware crates: `cargo build --release` and report `cargo size --release` (text/data/bss) before and after

## Lint rules
- Clippy messages from `clippy.toml` say how to fix the problem. Fix the root cause.
- No `unwrap()`. Propagate errors with `?`, or handle them.
- If a lint genuinely doesn't apply, use `#[expect(clippy::name, reason = "...")]` with a reason a
  reviewer would accept, and call it out in your summary. Never a bare `#[allow]`.
- Every `unsafe` block needs a `// SAFETY:` comment stating the invariant that makes it sound.
- Never edit `clippy.toml`, the `[lints]` tables, or `rust-toolchain.toml` to get a check passing.

## Hardware safety
- Never run `cargo run`/`cargo embed`/`probe-rs run` on a target (that flashes the board), and never run
  anything that drives motors, unless I ask.
