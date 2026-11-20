# Setup guide

Do **Phase 1** once per machine, then **Phase 2** once per project with the profile that fits it.
Every step ends in a **Verify** with the expected result. Written so a person or a coding agent can
follow it.

## Rules for an agent following this guide

- Work in one project at a time, on a new branch (`git switch -c dev-env-setup`). Don't commit to
  main or push without being asked.
- Steps marked **STOP (human)** need a person: signing in, choosing hardware settings, anything that
  flashes a board, opens a device port or moves an actuator. Pause and ask.
- Never edit a lint config to make a check pass. Report the failure.
- At the end of each phase, report every Verify command and its result.

To hand a phase to an agent, open the project and say: *"Follow Phase 2 of ~/dev-tooling/docs/SETUP.md
for this repo with the firmware profile. Stop at every STOP (human) step."*

## Prerequisites

| Tool | Needed for | Ubuntu | Arch / Omarchy | macOS | Windows |
| --- | --- | --- | --- | --- | --- |
| git, Python 3.10+ | everything | `apt install git python3` | `pacman -S git python` | `brew install git python` | Git for Windows (gives Git Bash) + python.org |
| uv | lint tools | `curl -LsSf https://astral.sh/uv/install.sh \| sh` | `pacman -S uv` | `brew install uv` | `winget install astral-sh.uv` |
| 1Password CLI `op` (optional) | agent App keys | 1password.com/downloads/command-line | `yay -S 1password-cli` (AUR) | `brew install --cask 1password-cli` | `winget install AgileBits.1Password.CLI` |
| GitHub CLI `gh` | PRs, agent roles | `apt install gh` | `pacman -S github-cli` | `brew install gh` | `winget install GitHub.cli` |
| VS Code (Microsoft build) | editor | .deb from code.visualstudio.com | `yay -S visual-studio-code-bin` (not the `code` OSS package) | `brew install --cask visual-studio-code` | `winget install Microsoft.VisualStudioCode` |
| Docker | ROS 2 | docs.docker.com | `pacman -S docker docker-buildx`, `systemctl enable --now docker.socket` | Docker Desktop | Docker Desktop (WSL2 backend) |
| Arm GNU toolchain, CMake, Ninja, OpenOCD | C/C++ firmware | `apt install cmake ninja-build openocd` + Arm toolchain | `pacman -S arm-none-eabi-gcc arm-none-eabi-newlib cmake ninja openocd` | `brew install --cask gcc-arm-embedded; brew install cmake ninja open-ocd` | Arm toolchain installer + `winget install Kitware.CMake Ninja-build.Ninja` |
| rustup, probe-rs | Rust | rustup.rs, probe.rs | `pacman -S rustup`, probe-rs from probe.rs | rustup.rs, probe.rs | rustup.rs, probe.rs |
| typst, typstyle | Typst docs | `cargo install typst-cli typstyle --locked` | `pacman -S typst typstyle` | `brew install typst typstyle` | `winget install Typst.Typst`, `cargo install typstyle --locked` |
| Node.js 22.13+ or 24+, and npm | Astro sites | nodejs.org (LTS; the apt package can be too old) | `pacman -S nodejs npm` | `brew install node` | `winget install OpenJS.NodeJS.LTS` |

On Arch/Omarchy, use the Microsoft VS Code build. The open-source `code` package can't install
Pylance, the C/C++ debugger, Remote-SSH or Dev Containers. On Arch, ROS 2 runs in the dev container.
On Windows, run the scripts from Git Bash; ROS 2 runs in Docker Desktop or WSL2.

## Phase 1: Machine (once per machine)

```bash
git clone git@github.com:knowingwings/dev-tooling.git ~/dev-tooling
~/dev-tooling/scripts/install-machine.sh
```

This script installs pre-commit, ruff and clang-tidy (20+) with uv. It installs the VS Code
extensions into the **ROS2** and **Firmware** profiles. It also links `vscode/user/settings.json`
into VS Code, so `git pull` in the kit updates your settings on every machine. The script keeps a
backup of your existing settings next to the link. On Windows without Developer Mode it copies instead; re-run after each pull.

**STOP (human):**
1. VS Code > gear > Profiles: for ROS2 and Firmware, set *Settings* to "Use Default".
2. Log in to Claude Code (Claude icon in the sidebar).
3. Settings Sync is optional now. If you keep it on, exclude *Settings* so it doesn't fight the link.

Keep `arm-none-eabi-gdb`, `openocd` and `JLinkGDBServerCLExe` on PATH: Cortex-Debug finds them there,
so no machine-specific paths go into the shared settings file.

**Verify:**

| Check | Expected |
| --- | --- |
| `clang-tidy --version` | LLVM 20 or newer, from `~/.local/bin` |
| `pre-commit --version`, `ruff --version` | both print a version |
| `code --profile ROS2 --list-extensions \| wc -l` | 18 or more |
| VS Code settings file | a link to `~/dev-tooling/vscode/user/settings.json` (Windows without Developer Mode: a copy) |

## Phase 2: Project (once per project)

```bash
cd <repo> && git switch -c dev-env-setup
~/dev-tooling/scripts/adopt.sh <profile> <repo>
```

| Profile | For |
| --- | --- |
| `ros2` | colcon workspaces and ROS 2 packages (C++ and Python) |
| `firmware` | embedded C/C++ with CMake and arm-none-eabi-gcc |
| `rust` | host Rust: tools, services, ROS 2 nodes |
| `rust-embedded` | `no_std` firmware with probe-rs |
| `python` | standalone Python: test rigs, HIL scripts, serial/CAN tools |
| `typst` | Typst documents |
| `astro` | Astro websites (TypeScript, MDX) |

`adopt.sh` copies the profile's files, and it does not overwrite a file that exists. It builds
`AGENTS.md` (the shared rules and this stack's section) and a `CLAUDE.md` that imports it. It pins
the kit's hooks to the kit version and adds `.gitignore` entries. Then it writes
`.dev-tooling-version` and installs the git hooks. It ends with a
**Still to do** list for that profile: do those steps (details below).

Every profile also gets the GitHub conventions (see "GitHub conventions" below):
- an evidence-first PR template
- issue templates: Task, Bug, and Agent mistake → check
- CODEOWNERS for the files that define the checks
- a `pr-checks` workflow
- `docs/FEATURE_MAP.md`, for you to fill in

Files it skipped because they already exist: compare with
`adopt.sh <profile> <repo> --diff` and merge by hand. If you kept your own `CLAUDE.md`, make
`@AGENTS.md` its first line.

### ros2

- For a repo of packages cloned into a workspace (`~/ros2_ws/src/<repo>`), add
  `--workspace ~/ros2_ws` so `.vscode/` and `.devcontainer/` go to the workspace root.
- In every `ament_cmake` package, add the warning flags and replace the `BUILD_TESTING` block with
  `lint/ros2/cmake-snippet.cmake`. In `ament_python` packages, delete `test/test_flake8.py` and
  `test/test_pep257.py`.
- Not on Jazzy: change the distro in `.devcontainer/Dockerfile`, `.devcontainer/devcontainer.json`
  and `.vscode/settings.json` (Humble uses `python3.10`), and `target-version` in `ruff.toml`.
- **STOP (human):** open the workspace root in VS Code (ROS2 profile) and run *Dev Containers: Reopen
  in Container* (always on Arch; optional on Ubuntu). Then `Ctrl+Shift+B` to build.
- Talking to a real robot: `export ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET` (terminals default to
  localhost). From a container, that only works on a Linux host.

**Verify:** new terminal prompt starts `(ros2 jazzy)`; `build/compile_commands.json` exists and `F12`
on an `rclcpp::` symbol works; `colcon test` results unchanged.

### firmware

- `CMakeLists.txt`: `set(CMAKE_EXPORT_COMPILE_COMMANDS ON)`, `include(cmake/warnings.cmake)`,
  `fw_strict_warnings(<your target>)` (never on vendor HAL targets),
  `target_link_options(<target> PRIVATE -Wl,--print-memory-usage)`.
  If `-Werror` breaks the existing build: **STOP (human)** and choose between fixing, applying it to
  clean modules only, or dropping `-Werror` temporarily.
- `patterns.toml`: rename `bsp/`, `drivers/`, `Drivers/` to your layout; non-STM32 MCUs need their
  peripheral names in `fw-register-access-outside-bsp`; delete `fw-no-double` on a double-precision FPU.
- `.clang-tidy`: add the toolchain's include paths to `ExtraArgs`
  (`arm-none-eabi-gcc -xc -E -v /dev/null` lists them).
- **STOP (human):** set the probe, MCU and SVD file in `.vscode/launch.json` and the flash task.
  Motor boards: set the timer debug-freeze bits before debugging with power on (a breakpoint halts
  the CPU, not the PWM).

**Verify:** `cmake --build build` prints FLASH/RAM usage; `main.c` has no clangd errors;
`pre-commit run clang-tidy --hook-stage pre-push --all-files` runs without `stdint.h not found`.

### rust / rust-embedded

- Merge `lint/rust/Cargo-lints.toml` into the workspace `Cargo.toml` and add `[lints] workspace = true`
  to each crate (single crate: rename the headers to `[lints.rust]` / `[lints.clippy]`). HAL crates that
  need `unsafe` get their own `[lints]` table.
- Set `channel` in `rust-toolchain.toml` to your current `rustc --version`, and `edition` in
  `rustfmt.toml` to match your crates.
- `unwrap_used = "deny"` flooding existing code: **STOP (human)**, fix or set it to `"warn"`.
- rust-embedded: set `rust-analyzer.cargo.target`; **STOP (human):** set `chip` and `svdFile` in
  `.vscode/launch.json`; delete `clippy.toml` entries for crates you don't use.

**Verify:** `cargo clippy --workspace --all-targets -- -D warnings` runs and
`cargo clippy 2>&1 | grep -iE "unknown field|does not refer"` prints nothing.

### python

- If `pyproject.toml` was skipped, merge `[dependency-groups]` and the `[tool.*]` sections from
  `lint/python/pyproject.toml`. Then `uv sync`.
- Mark tests that touch a device `@pytest.mark.hardware`; plain `uv run pytest` skips them.

**Verify:** `uv run pyright` runs (hundreds of errors on old code: **STOP (human)**, consider
`typeCheckingMode = "basic"`); `uv run pytest` shows hardware tests deselected.

### typst

- List the documents to build in `.typst-entries` (defaults to `main.typ`).
- Commit the fonts your documents use to `fonts/`. The build ignores system fonts, so a PDF looks
  the same at work and at home. If a font is missing, the build fails and tells you the fix.
- `.typst-version` pins the compiler. Upgrade it in its own commit and check the PDFs.

**Verify:** `pre-commit run typst-compile --hook-stage pre-push --all-files` prints `ok <doc>` for
each document; Tinymist preview opens with `Ctrl+K V`.

### astro

- Install the tools that the checks use, as dev dependencies. These versions work together:
  `npm install --save-dev @astrojs/check typescript@~6.0 eslint@^10 @eslint/js@^10 typescript-eslint eslint-plugin-astro eslint-plugin-jsx-a11y-x prettier prettier-plugin-astro`.
  Commit `package.json` and `package-lock.json`.
- TypeScript stays on 6.0 until `typescript-eslint` supports a later version. `eslint-plugin-jsx-a11y-x`
  is the maintained fork of `eslint-plugin-jsx-a11y` that supports ESLint 10.
- On each machine, run `npm ci` before you commit, because the hooks run the tools from `node_modules`.
- Existing code can fail `prettier --check`. Format it with `npx --no-install prettier --write .` in its
  own commit.

**Verify:** `./check --list` shows hooks, eslint, prettier, astro-check and build;
`npx --no-install eslint .` and `npx --no-install astro check` run without a config error.

## GitHub conventions (each project)

**STOP (human), once per repo on GitHub:** go to Settings > Branches and add a rule for `main`.
Require a pull request. Require the `pr-checks` and CI status checks to pass. Require a review from
Code Owners. Without this rule, the checks below give advice but do not stop a merge.

| Convention | Enforced by | Example |
| --- | --- | --- |
| Branch `<type>/<short-description>`, or an agent prefix (`claude/...`) | `check-branch` hook (pre-push) and `pr-checks` | `feat/motor-current-limit`, `fix/123-imu-timestamp` |
| No direct pushes to `main` | `check-branch` hook, branch protection | open a PR instead |
| PR title is a Conventional Commit (it becomes the squash-merge commit) | `pr-checks` | `fix(imu): use sensor timestamp for fusion` |
| PR **Evidence** filled in, exactly one **Risk** box ticked | `pr-checks` | test output, sim/bag run, plot, before/after |
| Changes to the checks (lint configs, `AGENTS.md`, `.github/`) in their own PR, except a kit adoption or update (it changes `.dev-tooling-version`) | `pr-checks`, CODEOWNERS | `chore(lint): ban HAL_Delay outside init` |

The workflow is trunk-based: short branches merged into `main` with squash merges, releases cut from
`v*` tags. To keep a `develop` integration branch, add it to `protected_branches` in the `[git]` table
of `patterns.toml` and point PRs at it.

Fill in `docs/FEATURE_MAP.md` early: one row per behaviour, with the command that proves it works.
It's what agents run to produce PR evidence, and what you check that evidence against.

When an agent makes the same mistake twice, open an **Agent mistake → check** issue. Then turn the
mistake into a rule. Put the rule here, or in dev-tooling if every project needs it.

## Writing and secrets checks (each project)

Every profile gets three more hooks. They run on commit, and `./check` runs them too.

- `typos` checks the spelling in Markdown, Typst, rst and text files. `_typos.toml` sets British
  English. Put names from code or products in backticks, or add them to `[default.extend-words]`.
  In `.typ` files, typos accepts the Typst words `center`, `color` and `gray`, because it can't tell
  Typst code from prose.
- `check-prose` checks the ASD-STE100 length rules on the doc blocks that you change. A descriptive
  sentence has 25 words or fewer, and a numbered step has 20 words or fewer. A paragraph has 6
  sentences or fewer. A problem that the doc already had is not reported when the change keeps its
  length, for example a spelling fix. Use `[prose]` in `patterns.toml` to change the paths or the limits.
- `check-secrets` stops private keys and known token formats. It also stops literal values for
  secret variables in env files.

To keep a secret out of git, put an `op://` reference in the env file. Then run the command with
`op run --env-file=<file> -- <command>`.

## One command: `./check`

Every project gets a `./check` script. It runs all of the project's checks and prints one line per
step. When a step fails, it also prints the failing lines and a log path:

```
PASS  hooks            2.1s
FAIL  clippy           0.9s  14 error line(s)
      error: used `unwrap()` on a `Result` value
         --> crates/app/src/main.rs:23:13
      ... 12 more
      full log: .dev-check/clippy.log
PASS  test             4.2s  ok. 31 passed; 0 failed
```

`./check --quick` skips slow steps, `./check --list` shows them, `./check --only test` runs one. The
steps live in `[[check.step]]` tables in `patterns.toml`, so a project can add its own (a sim smoke
test, a bag replay). `./check` runs the dev-tooling version the project adopted (it needs `uv`), so
results match on every machine. Agents paste its summary into the PR's Evidence section.

## Agent roles (GitHub Apps)

There are four roles: **architect**, **builder**, **reviewer** and **publisher**. Each role is a
GitHub App that you own. The full instructions are in each project's `docs/agents/`, and Claude Code
also has them as subagents in `.claude/agents/`. Apps are free, and they use short-lived tokens with
only the permissions they need. Each App shows as `<name>[bot]` on every PR, review and commit.

A reviewer App's approval counts toward "required approvals". An App can't be a code owner, so a
change to the checks always needs your approval.

**STOP (human), once per role** (about 5 minutes each):

1. GitHub > Settings > Developer settings > GitHub Apps > **New GitHub App**.
   - Name: `<you>-<role>` (e.g. `knowingwings-reviewer`); homepage: your profile URL.
   - Webhook: untick **Active**.
   - Repository permissions (everything else: No access):

     | Role | Contents | Pull requests | Issues | Administration | Checks |
     | --- | --- | --- | --- | --- | --- |
     | architect | Read | Read | Read and write | | |
     | builder | Read and write | Read and write | Read | | Read |
     | reviewer | Read | Read and write | Read and write | | Read |
     | publisher | Read and write | Read and write | Read and write | Read | Read |

   - Where can it be installed: **Only on this account**. Create.
2. Copy the **Client ID**, then **Generate a private key**.
3. Store the key. **Recommended: 1Password.** Nothing sits on disk, and every machine gets the same keys:
   - In 1Password, create an item named `<you>-<role>`, for example in a `Dev` vault. Add a text
     field `client_id` that holds the Client ID. Rename the downloaded key file to `private-key.pem`
     and attach it to the item. Then delete the download.
   - On each machine that runs agents (needs the 1Password CLI, `op`, signed in):
     ```bash
     mkdir -p ~/.config/dev-tooling/agents && cd ~/.config/dev-tooling/agents
     printf 'CLIENT_ID=op://Dev/<you>-<role>/client_id\nKEY=op://Dev/<you>-<role>/private-key.pem\n' > <role>.env
     ```
     `as-agent` reads the key through `op` only when it needs a new token, about once an hour per
     repo. It signs with the key, and then deletes it immediately. To keep the 1-hour tokens off disk
     too, set `DEV_TOOLING_NO_TOKEN_CACHE=1`. Then 1Password asks you to unlock it more often.

   **Or as a file** (no 1Password):
   ```bash
   mkdir -p ~/.config/dev-tooling/agents && cd ~/.config/dev-tooling/agents
   mv ~/Downloads/<app-name>.*.private-key.pem <role>.pem && chmod 600 <role>.pem
   echo 'CLIENT_ID=<client id>' > <role>.env
   ```
4. App page > **Install App** > your account > choose the repositories.
5. `as-agent setup <role>`: looks up the bot identity and saves it.

Once, for attribution: create `~/.config/dev-tooling/agents/owner.env` with
`OWNER_NAME="Your Name"` and `OWNER_EMAIL="<id>+<login>@users.noreply.github.com"` (GitHub > Settings
> Emails shows your noreply address). Every commit made through `as-agent` then carries
`Co-authored-by: you`, and CI requires `Requested-by: @you` on PRs opened by a bot.

**Verify:** `as-agent whoami reviewer` prints `<you>-reviewer[bot]`, and in a project
`as-agent reviewer gh api user` fails while `as-agent reviewer gh pr list` works (Apps aren't users).

## Auto-merge

A low-risk pull request merges itself when every required check passes and all of these are true:
- The Risk box is **Low**.
- Someone other than the author approved it (the reviewer bot counts), and nobody requested changes.
- It does not change the checks themselves.
- It has no `do-not-merge`, `needs-human` or `hold` label.

Medium-risk and high-risk pull requests always wait for you.

**STOP (human), once per repo:**
1. Settings > General > Pull Requests: tick **Allow auto-merge**, **Allow squash merging** and
   **Automatically delete head branches**.
2. Go to Settings > Branches and edit the rule for `main`. Set these options:
   - require a pull request with **1 approval**
   - **dismiss stale approvals**
   - **require review from Code Owners**
   - **require status checks**: `pr-checks` and your CI

   The workflow does nothing until required checks exist. Thus "merge when green" can never become
   "merge now".
3. Go to Settings > Secrets and variables > Actions. Add these settings:
   - the variable `PUBLISHER_CLIENT_ID`
   - the secret `PUBLISHER_PRIVATE_KEY`, which is the publisher App's key

   With these settings, merges show as the publisher bot and start workflows on `main`. Without them,
   the workflow token does the merge, and workflows on `main` do not start.

Turn it off per repo with `automerge = false` in the `[git]` table of `patterns.toml`.

## Phase 3: Smoke test (each project)

Add one deliberately bad line, try to commit, and check the commit is blocked with a message that says
how to fix it. Then `git restore --staged <file> && git checkout -- <file>`.

| Profile | Bad line | Expected |
| --- | --- | --- |
| any (C/C++/Rust/Python) | `// tweak gain for the new motor` (`#` in Python) | `no-comments` |
| ros2 (C++ in `src/`) | `auto t = create_wall_timer(1s, []{});` | `ros-no-wall-timer` |
| firmware (app code) | `HAL_Delay(10);` | `fw-no-blocking-delay` |
| rust | `std::thread::sleep(std::time::Duration::from_millis(1));` | clippy `disallowed_methods` (run `cargo clippy`) |
| python | `import os` then `os.system("ls")` | ruff `TID251` |
| typst | `#set text(font: "Arial")` | typst-compile font failure (on push) |
| astro (a page in `src/pages/`) | `<img src="/a.png" />` | eslint `astro/jsx-a11y/alt-text` |
| any | commit on a branch named `my-changes`, then `git push` | `check-branch` asks for `<type>/<short-description>` |
| any | `./check` on a clean checkout | one line per step, ending `N passed, 0 failed` |

## Updating a project to a newer kit

1. Run `git -C ~/dev-tooling pull` to get the new kit version.
2. Run `~/dev-tooling/scripts/adopt.sh <profile> <repo>`. It copies only the new files.
3. Run the same command with `--diff`. It shows how your copies differ from the kit.
4. Merge the changes you want. `AGENTS.md` and `.pre-commit-config.yaml` usually need a merge.
5. Make sure that `rev:` for dev-tooling in `.pre-commit-config.yaml` is the new tag.
6. Run `pre-commit run --all-files`, and then commit the update on its own branch.

Read `CHANGELOG.md` for the changes in each version.

## Daily workflow

- Give the agent the task on a branch; it reads `AGENTS.md` (via `CLAUDE.md` for Claude Code).
- In code you're still learning, trace it yourself first (`Shift+Alt+H` call hierarchy, `Shift+F12`
  references), then ask the agent to check your understanding.
- Review the agent's evidence (check output, tests, FLASH/RAM change) before its diff.
- Correct the same mistake twice → make it a check: `CustomFunctions` (clang-tidy),
  `disallowed-methods` (clippy), `banned-api` (ruff), or a `patterns.toml` rule for folder-specific
  rules. Add it to the kit with a fixture (see the README) so every project gets it.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| clang-tidy ignores `CustomFunctions` / unknown `ExcludeHeaderFilterRegex` | clang-tidy older than 20: put `~/.local/bin` first on PATH |
| Firmware clang-tidy: `'stdint.h' file not found` | add the toolchain include paths to `.clang-tidy` |
| `check-comments is not present in repository` | `pre-commit clean`, then retry (cached older kit version) |
| clangd errors everywhere in a ROS workspace | build once (`Ctrl+Shift+B`) to create `build/compile_commands.json` |
| `ros2: command not found` in the Claude panel | use the dev container, or start VS Code with `code .` from a sourced terminal |
| VS Code on Arch can't find Pylance / Dev Containers | you have the OSS build: `yay -S visual-studio-code-bin` |
| Typst: `This repo pins Typst X but you have Y` | install that version, or bump `.typst-version` in its own commit |
| Typst: `uses a font that isn't in fonts/` | commit the font to `fonts/` or use a built-in font |
| OpenOCD `LIBUSB_ERROR_ACCESS` / probe-rs permission denied | install the probe's udev rules, then replug |
