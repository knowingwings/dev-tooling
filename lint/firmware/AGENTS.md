## Embedded C/C++ firmware (this repo)

### Checks to run
- `./check` runs every check (hooks, build (with FLASH/RAM), clang-tidy, host-tests) and prints one line per step, with the failing lines
  and a log path when something fails. Paste its summary into the PR's Evidence section.
- `./check --quick` skips the slow steps while you iterate; run the full `./check` before you say
  you're done. `./check --list` shows exactly what runs.
- Report the FLASH and RAM lines from the build step before and after your change.

### Layout rules (enforced by the check-patterns hook)
- Register and peripheral access only in `bsp/` and `drivers/`. App code calls driver functions.
- No heap, no blocking delays outside init, no wait loops without a timeout, single-precision float only.
- Don't edit `.clang-tidy`, `patterns.toml` or `cmake/warnings.cmake`, or add `#pragma GCC diagnostic`,
  to pass a check.
