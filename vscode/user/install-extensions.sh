#!/usr/bin/env bash
# Creates two VS Code profiles (ROS2, Firmware) with only the extensions each needs,
# so each window stays fast and uncluttered. Run once per machine; Settings Sync keeps them in step after.
#
#   bash install-extensions.sh          # VS Code
#   CODE=cursor bash install-extensions.sh   # if you ever try Cursor
#
# Windows (PowerShell): run the same `code --profile ... --install-extension ...` lines.
set -euo pipefail
CODE="${CODE:-code}"

COMMON=(
  anthropic.claude-code                    # Claude Code
  llvm-vs-code-extensions.vscode-clangd    # C/C++ navigation, completion, live clang-tidy
  ms-vscode.cpptools                       # only for the gdb debugger (IntelliSense disabled in settings)
  ms-vscode.cmake-tools
  charliermarsh.ruff
  ms-python.python
  ms-python.vscode-pylance
  usernamehw.errorlens                     # lint errors shown inline on the line
  mhutchie.git-graph
  redhat.vscode-yaml
  redhat.vscode-xml
  ms-vscode-remote.remote-ssh              # edit/debug on the robot itself
  ms-vscode-remote.remote-containers       # dev containers
  rust-lang.rust-analyzer                  # Rust: navigation, completion, live clippy
  vadimcn.vscode-lldb                      # CodeLLDB: debugger for host Rust (and C++ if you prefer lldb)
  tamasfe.even-better-toml                 # Cargo.toml / pyproject.toml with schema validation
  myriad-dreamin.tinymist                  # Typst: completion, live preview, typstyle formatting
)

ROS2=(
  Ranch-Hand-Robotics.rde-pack             # ROS 2 + URDF tools (successor to the deprecated ms-iot.vscode-ros)
)

FIRMWARE=(
  marus25.cortex-debug                     # SWD debugging, peripheral registers (SVD), RTOS views, RTT
  ms-vscode.vscode-serial-monitor
  ms-vscode.hexeditor
  probe-rs.probe-rs-debugger               # embedded Rust: flash, debug, RTT/defmt over any probe
)

# Recent VS Code versions only create a profile when a window opens with it, and
# `--install-extension --profile X` fails with "Profile 'X' not found" until then.
ensure_profile() {
  local profile="$1"
  "$CODE" --profile "$profile" --list-extensions >/dev/null 2>&1 && return 0
  echo "[$profile] creating profile (opens a VS Code window; close it afterwards)"
  "$CODE" --profile "$profile" --new-window
  for _ in $(seq 1 30); do
    "$CODE" --profile "$profile" --list-extensions >/dev/null 2>&1 && return 0
    sleep 2
  done
  echo "[$profile] profile was not created; open VS Code > Profiles > New Profile '$profile', then re-run" >&2
  return 1
}

install() {
  local profile="$1"; shift
  ensure_profile "$profile"
  for ext in "$@"; do
    echo "[$profile] $ext"
    "$CODE" --profile "$profile" --install-extension "$ext" --force >/dev/null
  done
}

install "ROS2" "${COMMON[@]}" "${ROS2[@]}"
install "Firmware" "${COMMON[@]}" "${FIRMWARE[@]}"

echo "Extensions installed into the ROS2 and Firmware profiles."
