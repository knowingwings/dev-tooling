#!/usr/bin/env bash
# Run after colcon build (the build tasks do this). Two jobs:
#  1. Merge colcon's per-package compile_commands.json into build/compile_commands.json for clangd.
#  2. Write .vscode/ros.env (the sourced ROS environment) for the "launch node under gdb" debug config.
set -euo pipefail
WS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$WS"

python3 - <<'EOF'
import glob, json
entries = []
for db in sorted(glob.glob("build/*/compile_commands.json")):
    with open(db) as f:
        entries += json.load(f)
with open("build/compile_commands.json", "w") as f:
    json.dump(entries, f, indent=1)
print(f"post_build: merged {len(entries)} compile commands for clangd")
EOF

# colcon's setup scripts read unset variables (e.g. COLCON_TRACE), so relax -u while sourcing.
# shellcheck disable=SC1091
if [ -f install/setup.bash ]; then set +u; source install/setup.bash; set -u; fi
env | grep -E '^[A-Za-z_][A-Za-z0-9_]*=' | grep -vE '^(PS1|_|OLDPWD|SHLVL)=' > .vscode/ros.env
echo "post_build: wrote .vscode/ros.env"
