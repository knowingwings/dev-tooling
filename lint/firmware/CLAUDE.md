# Working in this repo

## Layout rules (enforced by the check-patterns hook)
- Register and peripheral access only in `bsp/` and `drivers/`. App code calls driver functions.
- No heap, no blocking delays outside init, no unbounded wait loops, single-precision float only.

## Before you say a change is done
Run these and include a short summary of the output in your final message:

1. `pre-commit run --files <files you changed>`
2. `cmake --build build` (warnings are errors), and report the `--print-memory-usage` FLASH/RAM lines
   before and after your change
3. `pre-commit run clang-tidy --hook-stage pre-push --files <changed .c files>`
4. Host unit tests: `ctest --test-dir build-host --output-on-failure`

## Lint rules
- Lint messages say how to fix the problem. Fix the root cause.
- Never edit `.clang-tidy`, `patterns.toml`, `warnings.cmake` or add `#pragma GCC diagnostic` to get a check passing.
- `lint-allow(<rule-id>): <reason>` is only for cases where the rule genuinely doesn't apply.
  Call it out in your summary so I can review it.

## Hardware safety
- Never flash a board, change option bytes/fuses, or run anything that drives motors unless I ask.
