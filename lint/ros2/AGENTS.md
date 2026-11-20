## ROS 2 (this repo)

### Checks to run
- `./check` runs every check (hooks, build, clang-tidy, test) and prints one line per step, with the failing lines
  and a log path when something fails. Paste its summary into the PR's Evidence section.
- `./check --quick` skips the slow steps while you iterate; run the full `./check` before you say
  you're done. `./check --list` shows exactly what runs.

### Conventions
- Timers and timestamps use the node clock (`create_timer`, `now()`), so sim time and bag replay work.
- No blocking sleeps or spinning inside callbacks. Spinning belongs in `main()`.
- QoS comes from a named profile, never a bare queue depth.
- Log with `RCLCPP_*` / `get_logger()` (the `_THROTTLE` variants in loops), never `cout` or `print`.
- Don't edit `.clang-tidy`, `ruff.toml`, `patterns.toml` or the CMake warning flags to pass a check.
