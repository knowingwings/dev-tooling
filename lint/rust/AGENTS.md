## Rust (this repo)

### Checks to run
1. `cargo fmt --all`
2. `cargo clippy --workspace --all-targets -- -D warnings`
3. `cargo test --workspace`
4. Firmware crates: `cargo build --release`, and report `cargo size --release` (text/data/bss) before
   and after your change.

### Conventions
- No `unwrap()`. Propagate errors with `?`, or handle them.
- Suppress a lint only with `#[expect(clippy::name, reason = "...")]`, never a bare `#[allow]`.
- Every `unsafe` block needs a `// SAFETY:` comment stating the invariant that makes it sound.
- `cargo run`, `cargo embed` and `probe-rs run` flash the board when a target is set: see Hardware safety.
- Don't edit `clippy.toml`, the `[lints]` tables or `rust-toolchain.toml` to pass a check.
