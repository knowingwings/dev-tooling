## ROS 2 (this repo)

### Checks to run
1. `pre-commit run --files <files you changed>`
2. `colcon build --packages-up-to <pkg>` (warnings are errors)
3. `pre-commit run clang-tidy --hook-stage pre-push --files <changed .cpp files>`
4. `colcon test --packages-select <pkg> && colcon test-result --verbose`

### Conventions
- Timers and timestamps use the node clock (`create_timer`, `now()`), so sim time and bag replay work.
- No blocking sleeps or spinning inside callbacks. Spinning belongs in `main()`.
- QoS comes from a named profile, never a bare queue depth.
- Log with `RCLCPP_*` / `get_logger()` (the `_THROTTLE` variants in loops), never `cout` or `print`.
- Don't edit `.clang-tidy`, `ruff.toml`, `patterns.toml` or the CMake warning flags to pass a check.
