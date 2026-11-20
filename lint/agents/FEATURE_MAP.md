# Feature map

Every behaviour this project has, seen from the outside, and how to prove it still works. Agents and
people use it the same way. When a change touches a feature, run that feature's check and put the
result in the PR's **Evidence** section. A feature with no check is the next thing to fix.

Keep one row per behaviour someone would notice if it broke. Prefer checks that a command can run
over checks that need a person; mark the ones that need hardware.

| Feature | Entry points | How to verify | Needs hardware | Evidence to attach |
| --- | --- | --- | --- | --- |
| *Example:* IMU fusion publishes `/odom` at 100 Hz | `imu_fusion` node, `fusion.launch.py` | `ros2 launch pkg replay.launch.py bag:=test/bags/turn.mcap` then `ros2 topic hz /odom` | no (bag replay) | rate and yaw-drift plot vs. the previous release |
| *Example:* motor controller holds current limit | `app/motor.c`, `bsp/pwm.c` | `ctest -R current_limit` (host), then bench script `tools/bench/current_step.py` | bench for the second step | ctest output; scope capture of a 10 A step |
| *Example:* charge attack timing | `mobile_knight_core::combat` | `cargo test -p mobile_knight_core combat::` | no | test output; short screen recording of perfect / under / over charge |

## Verification environments

| Environment | How to start it | What it can prove |
| --- | --- | --- |
| *Example:* simulation | `ros2 launch pkg sim.launch.py` | motion planning, behaviour trees |
| *Example:* bag replay | `ros2 bag play test/bags/<name>.mcap --clock` | perception, fusion, timing against recorded data |
| *Example:* host tests | `ctest --test-dir build-host` / `cargo test` / `uv run pytest` | logic with the hardware faked |
| *Example:* bench (needs a person) | power supply current-limited to 2 A, motor unloaded | drivers, timing, current limits |
