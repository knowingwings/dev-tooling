## Embedded C/C++ firmware (this repo)

### Checks to run
1. `pre-commit run --files <files you changed>`
2. `cmake --build build` (warnings are errors). Report the `--print-memory-usage` FLASH and RAM lines
   before and after your change.
3. `pre-commit run clang-tidy --hook-stage pre-push --files <changed .c files>`
4. Host unit tests: `ctest --test-dir build-host --output-on-failure`

### Layout rules (enforced by the check-patterns hook)
- Register and peripheral access only in `bsp/` and `drivers/`. App code calls driver functions.
- No heap, no blocking delays outside init, no wait loops without a timeout, single-precision float only.
- Don't edit `.clang-tidy`, `patterns.toml` or `cmake/warnings.cmake`, or add `#pragma GCC diagnostic`,
  to pass a check.
