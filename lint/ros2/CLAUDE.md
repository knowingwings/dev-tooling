# Working in this repo

## Before you say a change is done
Run these and include a short summary of the output in your final message:

1. `pre-commit run --files <files you changed>`
2. `colcon build --packages-up-to <pkg>` (no warnings: they're errors)
3. `pre-commit run clang-tidy --hook-stage pre-push --files <changed .cpp files>`
4. `colcon test --packages-select <pkg> && colcon test-result --verbose`

## Lint rules
- Lint messages say how to fix the problem. Fix the root cause.
- Never edit `.clang-tidy`, `ruff.toml`, `patterns.toml` or CMake warning flags to get a check passing.
- `lint-allow(<rule-id>): <reason>` is only for cases where the rule genuinely doesn't apply.
  Call it out in your summary so I can review it.

## Hardware safety
- Never launch anything that commands real actuators (motors, arms, grippers) or flashes a board
  unless I ask. Use simulation or bag replay to verify.
