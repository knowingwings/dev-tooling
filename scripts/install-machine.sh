#!/usr/bin/env bash
# One-time setup for a machine (run again any time; it's safe to repeat).
#
#   scripts/install-machine.sh
#
# 1. Installs pre-commit, ruff and clang-tidy (20+) with uv
# 2. Installs VS Code extensions into the ROS2 and Firmware profiles
# 3. Symlinks this repo's user settings into VS Code, so `git pull` updates your settings
#    on every machine (an existing settings file is backed up first)
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CODE="${CODE:-code}"

echo "== 1. Command-line tools"
if command -v uv >/dev/null; then
  for t in pre-commit ruff clang-tidy; do uv tool install --quiet "$t" 2>/dev/null || uv tool upgrade --quiet "$t"; done
  uv tool update-shell >/dev/null 2>&1 || true
  echo "   pre-commit, ruff, clang-tidy installed in ~/.local/bin"
else
  echo "   uv not found: install it first (curl -LsSf https://astral.sh/uv/install.sh | sh), then re-run" >&2
fi

echo "== 2. VS Code extensions"
if command -v "$CODE" >/dev/null; then
  CODE="$CODE" bash "$KIT/vscode/user/install-extensions.sh" | grep -E '^\[' | cut -d' ' -f1 | sort | uniq -c \
    | awk '{print "   " $2 ": " $1 " extensions"}' 
else
  echo "   '$CODE' not on PATH: skipping (macOS: Command Palette > Shell Command: Install 'code' command in PATH)"
fi

echo "== 3. User settings"
OS="$(uname -s)"
case "$OS" in
  Linux)  BASE="${XDG_CONFIG_HOME:-$HOME/.config}" ;;
  Darwin) BASE="$HOME/Library/Application Support" ;;
  MINGW*|MSYS*|CYGWIN*) BASE="$(cygpath -u "$APPDATA" 2>/dev/null || echo "$APPDATA")" ;;
  *) BASE="" ;;
esac
# Official VS Code uses Code/; Arch's open-source `code` package uses "Code - OSS"/, VSCodium uses VSCodium/.
DIR=""
for flavour in "Code" "Code - OSS" "VSCodium"; do
  [[ -n "$BASE" && -d "$BASE/$flavour" ]] && { DIR="$BASE/$flavour/User"; FLAVOUR="$flavour"; break; }
done
[[ -z "$DIR" && -n "$BASE" ]] && { DIR="$BASE/Code/User"; FLAVOUR="Code"; }
if [[ "${FLAVOUR:-}" != "Code" && -n "$DIR" ]]; then
  echo "   WARNING: found the '$FLAVOUR' build, not Microsoft's VS Code. It can't install Pylance, the C/C++"
  echo "   debugger, Remote-SSH or Dev Containers (needed for ROS 2 on Arch). On Arch/Omarchy install the"
  echo "   official build instead: yay -S visual-studio-code-bin (then re-run this script)."
fi
if [[ -n "$DIR" ]]; then
  mkdir -p "$DIR"; S="$DIR/settings.json"; SRC="$KIT/vscode/user/settings.json"
  if [[ -L "$S" && "$(readlink "$S")" == "$SRC" ]]; then
    echo "   already linked: $S"
  else
    [[ -e "$S" ]] && mv "$S" "$S.backup-$(date +%F-%H%M%S)" && echo "   backed up existing settings next to it"
    case "$OS" in
      MINGW*|MSYS*|CYGWIN*)
        # Git Bash's ln -s silently copies unless native symlinks are allowed (Windows Developer Mode).
        if MSYS=winsymlinks:nativestrict ln -s "$SRC" "$S" 2>/dev/null; then
          echo "   linked $S -> $SRC"
        else
          cp "$SRC" "$S"
          echo "   COPIED (Windows wouldn't create a symlink): re-run this script after each git pull,"
          echo "   or turn on Windows Developer Mode and re-run to get a real link."
        fi ;;
      *) ln -s "$SRC" "$S" && echo "   linked $S -> $SRC" ;;
    esac
  fi
  echo "   Don't put machine-specific paths in it (it's shared via git). Cortex-Debug finds"
  echo "   arm-none-eabi-gdb, openocd and JLinkGDBServerCLExe on PATH, so keep those on PATH instead."
fi

echo
echo "STOP (human), once per machine:"
echo "  - VS Code > gear > Profiles: set Settings to 'Use Default' for ROS2 and Firmware"
echo "  - Log in to Claude Code (Claude icon in the sidebar)"
echo "  - Settings Sync is optional now (settings come from this repo); if you use it, exclude Settings to avoid conflicts"
echo "Then check: clang-tidy --version  (needs LLVM 20 or newer, from ~/.local/bin)"
