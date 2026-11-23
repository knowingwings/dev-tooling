# Changelog

## Unreleased

**New: `multiline` rules in `patterns.toml`**
- A rule with `multiline = true` is matched against the whole file, not one line at a time. Its
  hit, and its `lint-allow`, belong to the line where the match starts.
- Use it for code that a formatter splits over several lines. Rules without it work as before.

**Fixed: `fw-no-unbounded-wait` finds formatted wait loops (firmware profile)**
- The kit's `.clang-format` moves every loop body to its own line, so after formatting the rule
  found no wait loops at all. It is now a multiline rule.
- It flags a loop whose body is empty, `{}`, or only an idle call such as `__NOP()` or
  `tight_loop_contents()`. A condition that names a tick, timeout or deadline counts as bounded.

## v0.5.0 (2026-11-22)

**New: `main-guard` workflow (every profile)**
- GitHub Free has no branch protection for private repos, so nothing on GitHub can block a push to
  `main`. `main-guard` runs on every push to the default branch, and asks GitHub which pull request
  brought in each new commit.
- If a commit didn't come from a pull request merged into that branch, or the push was a
  force-push, the workflow fails and opens an issue. The issue reaches you even when a bot pushed.
- The `check-branch` pre-push hook still blocks direct pushes from machines with the kit's hooks.

**Changed: auto-merge works without branch protection**
- Before, the auto-merge workflow did nothing without branch protection. Now it waits until every
  other check on the pull request's last commit has passed, and then merges only that commit
  (`--match-head-commit`). A failed check stops it. A new push cancels the wait and starts again.
- With branch protection, it still uses GitHub's own auto-merge and required checks.
- The other rules are unchanged: Low risk, approved by someone other than the author, no changes to
  the checks, and no hold label. `automerge = false` in `[git]` still turns it off.

**Fixed: `test_as_agent.sh` never runs the real `op` CLI**
- The "missing op CLI" test set `PATH=/usr/bin:/bin` to hide `op`. On Arch Linux, `op` is in
  `/usr/bin`, so the test ran the real 1Password CLI, which can show an approval prompt, and then
  failed. The test now uses links to the system tools without `op`.

**Changed: the `astro-punctuation-own-line` fix uses an Astro comment**
- The rule's message now suggests `{/* prettier-ignore */}`. Prettier's Astro plugin honours it,
  and Astro leaves it out of the page. `<!-- prettier-ignore -->` works too, but it ships in the
  HTML.

## v0.4.2 (2026-11-22)

**Fixed: Prettier no longer changes YAML in astro repos**
- `.prettierignore` lists `*.yml` and `*.yaml`. The commit hooks never formatted YAML, but `./check`
  ran `prettier --check .`, so it failed on the kit's own hook config and workflows. Their aligned
  comments aren't Prettier style.

**New: `astro-punctuation-own-line` rule (astro profile)**
- Prettier's Astro plugin can put a punctuation mark on its own line when it wraps an element. The
  page then shows a space before the mark: `</a>.` becomes "LinkedIn .".
- The `check-patterns` hook now runs on `.astro` files and flags that line. Its message gives the
  fix: `<!-- prettier-ignore -->` before the element that holds the sentence.
- SETUP.md: after you format existing code, build the site before and after and compare the pages.

**Fixed: combined profiles keep the comments in VS Code files**
- When two profiles both have a `.vscode/*.json` file, the merged file now keeps every comment
  before the key or array element it describes. Before, only the comments at the top of the file
  were kept, so `astro,typst` lost the notes on `typescript.tsdk` and the Typst fonts.
- A comment inside an array goes when the first profile's array replaces that array. One-profile
  adoption is unchanged.

## v0.4.1 (2026-11-21)

**Changed: `check-comments` accepts moved and re-wrapped comments**
- A comment on an added line isn't new when its words are a run of words from comments that the same
  change removed from the file. So you can move a comment, re-indent it, or re-wrap it to fit the
  line length. You can also change the code in front of a trailing comment. Before, all of these
  failed, and agents moved the comment into a docstring or deleted it to get past the hook.
- A copied comment is still new, and so is a comment with any word added or changed. Each removed
  word excuses one added word, in the same file.

## v0.4.0 (2026-11-20)

**Changed: ruff accepts British typography (python and ros2 profiles)**
- `allowed-confusables`: en and em dashes, curly quotes, `×`, the minus sign `−`, primes and the
  no-break spaces. RUF001-003 flagged all of them in docstrings, comments and strings, for example
  `2–5 MB` and `l’élève`. Look-alike letters, such as a Cyrillic `а` in a Latin word, are still
  flagged.

**New: combine profiles in one repo**
- `adopt.sh astro,typst <repo>` adopts two profiles, the main one first. `AGENTS.md` gets both stack
  sections, and the files that both profiles have are merged: pre-commit hooks, `./check` steps and
  rules, and the VS Code extensions, settings, tasks and launch configurations. For other shared
  files, the first profile's copy is kept and listed.
- `--diff` compares with the merged files, so updating a combined repo works the same way.
- One-profile adoption is unchanged: all seven profiles give the same files and output as before.

**Changed: python commit hooks check the files you commit, with the project's own tools**
- The `pyright` hook checks the files you commit, as the `ruff` hook already did. `./check` and CI
  still check the whole project. Before, any commit with a Python file failed until the whole
  project had no pyright errors, so a repo with old errors couldn't be fixed in small commits.
- The `ruff` and `ruff-format` hooks run `uv run ruff`, the version in `uv.lock`. Before, they used
  ruff-pre-commit v0.8.6 while `./check` used the project's ruff, so the two could disagree (for
  example, the old version flagged `do_GET` in an `http.server` handler).

**New: `astro` profile, for Astro websites**
- ESLint 10 (JavaScript, `typescript-eslint`, Astro and accessibility recommended rules, and bans on
  `any`, `==` and `console.log`), Prettier with the Astro plugin, and `astro check` for types.
- `./check` runs hooks, eslint, prettier, astro-check and build. The tools are the project's dev
  dependencies, run with `npx --no-install`, so `package-lock.json` sets the versions.
- SETUP.md gives an install command with versions that work together: TypeScript 6.0 (for
  `typescript-eslint`) and `eslint-plugin-jsx-a11y-x` (accessibility rules that support ESLint 10).
  The tools need Node.js 22.13+ or 24+ (`prettier-plugin-astro` and ESLint 10).
- VS Code settings and tasks for the Astro, ESLint and Prettier extensions. `tests/run_tests.py`
  checks the rules against the fixtures in `tests/fixtures/astro`.
- `./check` removes colour codes from a step's output before it matches the `summary` and `errors`
  patterns, and in the log. `astro check` colours its output even when it isn't a terminal.
- SETUP.md: on Arch, typstyle is a pacman package (`pacman -S typst typstyle`).

## v0.3.1 (2026-11-20)

**Fixes: a project's adoption PR now passes the kit's own checks**
- `check-pr`: a PR that changes `.dev-tooling-version` (a kit adoption or update) can change the
  checks and other files together. `.dev-tooling-version` is now a protected path and in CODEOWNERS,
  so the owner reviews these PRs and auto-merge never takes them.
- `check-prose`: a problem that the old version of the doc already had is not reported when the
  change keeps the sentence or paragraph length. A spelling fix in a long paragraph no longer fails.
- `typos`: the Typst built-ins `center`, `color` and `gray` are accepted in `.typ` files. Before,
  every Typst document that used them failed.
- `typos`: HTML tags in docs are skipped, so CSS such as `style="text-align: center"` in a Markdown
  page passes. The text between the tags is still checked.
- `docs/FEATURE_MAP.md` template: split a 27-word sentence that failed `check-prose` on adoption.
- `./check`: `{changed}` compares with the remote's default branch (`origin/HEAD`), not always
  `origin/main`. In a repo whose default branch is `master`, the hooks step skipped with "nothing
  changed". Set `[check] base` to choose another branch.
- `typst-compile`: a repo with no entry documents passes without Typst installed. Before, `git push`
  failed with "typst not found" in a repo that had no Typst documents.

## v0.3.0 (2026-11-20)

**New: house style for docs, and secrets checks (merged from the owner's machine AGENTS.md)**
- AGENTS.md gains Writing (British English and ASD-STE100 for docs), Secrets (1Password CLI) and
  "Instructions, notes and memory" sections.
- `typos` hook with `_typos.toml` (locale `en-gb`): flags American spellings in Markdown, Typst, rst
  and text files. Code, inline code and fenced blocks are left alone.
- `check-prose` hook: STE length rules for Markdown and Typst docs (25 words per descriptive
  sentence, 20 per numbered step, 6 sentences per paragraph), on changed blocks only.
  `lint-allow(prose): <reason>` in a comment above a block keeps it as it is. `[prose]` in
  `patterns.toml` sets paths and limits.
- `check-secrets` hook: blocks private keys, well-known token formats, and literal values for
  KEY/TOKEN/SECRET/PASSWORD variables in env files (use `op://` references and `op run`).
- The kit runs `typos`, `check-prose` and `check-secrets` on itself in CI. Its own docs are
  rewritten in STE so that they pass `check-prose`.

**Fixes**
- `as-agent` picked the Windows Store `python3` stub ("Python was not found") and failed with a
  misleading "GitHub rejected the JWT". It now uses the first `python3`, `python` or `py` that runs.

## v0.2.0 (2026-11-20)

**New: GitHub conventions, enforced (from Lauren Tan's evidence-over-diffs approach)**
- Every profile gets an evidence-first PR template (Evidence, Risk / blast radius, suppressions and
  rules learned), issue forms (Task with acceptance criteria and proof expected, Bug, Agent mistake →
  check), CODEOWNERS for the files that define the checks, and a `pr-checks` workflow.
- `check-branch` hook (pre-push): `<type>/<description>` branch names (agent prefixes allowed), no
  direct pushes to `main`.
- `check-pr` (CI): Conventional Commit PR titles, Evidence filled in, exactly one Risk box, and changes
  to the checks not mixed with other code.
- `docs/FEATURE_MAP.md` template: every behaviour and how to verify it, for agents to produce evidence.
- AGENTS.md gains Verification, "When you're corrected", and Git and pull requests sections.
- Trunk-based by default; `develop` can be added in `[git] protected_branches`.

**New: one command, agent roles and auto-merge (more of Lauren Tan's approach)**
- `./check` / `dev-check`: runs every check for the project and prints one line per step, with only
  the failing lines and a log path. Steps live in `[[check.step]]` in `patterns.toml`; `{changed}`
  expands to the files changed on the branch. Pinned to the adopted kit version via `uvx`.
- Agent roles as GitHub Apps you own: architect, builder, reviewer, publisher. Role docs in
  `docs/agents/`, Claude Code subagents in `.claude/agents/` (reviewer and publisher can't edit files).
- `as-agent <role> <command>`: runs git/gh as that role's App (short-lived token, bot identity, pushes
  over HTTPS with the App token) and adds the owner as `Co-authored-by` on every commit.
- `as-agent` can read App keys (and client IDs) from 1Password: `KEY=op://<vault>/<item>/<file>` in the
  role's env file. The key is fetched with `op` only when a token is needed, used to sign, and deleted.
  `DEV_TOOLING_NO_TOKEN_CACHE=1` also keeps the 1-hour tokens off disk.
- `check-pr` requires `Requested-by: @<person>` on PRs opened by a bot.
- `auto-merge` workflow: Low risk + approved by someone else + not changing the checks + no hold label
  → merges when green. Does nothing without branch protection and required checks. Uses the
  publisher App's token when configured.
- `.claude/` and `docs/agents/` count as check changes (CODEOWNERS, mixed-PR rule, never auto-merged).

**Fixes**
- `adopt.sh` exited silently in a repo with no `origin` remote.

## v0.1.0 (2026-11-20)

First version as a repo (previously two zips: dev-tooling, vscode-setup).

**New**
- `scripts/adopt.sh`: adds a profile to a project, never overwrites, pins hooks, writes `.dev-tooling-version`; `--diff` for updates.
- `scripts/install-machine.sh`: CLI tools, extensions, settings symlinked from the repo. Detects
  Code - OSS / VSCodium (Arch) and warns; Windows falls back to a copy when symlinks aren't allowed.
- `check-patterns` and `clang-tidy` are pre-commit hooks served from this repo, so projects no longer copy `tools/`.
- `check-comments` hook (from Lauren Tan's approach): blocks new comments on added lines; allows doc
  comments, `SAFETY:`, `REF(<source>): <fact>`, suppressions with a reason and licence headers.
  Tokenizer-based (strings, raw strings, Rust lifetimes, C++ digit separators), configured per project
  by `[comments]` in `patterns.toml`. The kit's own code follows it.
- Agent instructions moved to `AGENTS.md` (shared `lint/agents/base.md` + a section per stack) so any
  coding agent reads them; `CLAUDE.md` is `@AGENTS.md` plus Claude-only notes.
- `typst` profile: typstyle formatting on commit, and a `typst-compile` hook that builds every entry
  document with the Typst version pinned in `.typst-version` and no system fonts, failing on fonts
  that would render differently on another machine. Tinymist in VS Code with matching settings.
- Self-test: `tests/run_tests.py` (every rule against bad fixtures), `tests/test_adopt.sh`, GitHub Actions CI.

**Fixes found on a work machine**
- `clang_tidy.sh`: Windows / Git Bash support (path filters match `\` and drive letters; MSYS argument rewriting disabled).
- `check_patterns.py`: passes the kit's own Python rules (`git` resolved with `shutil.which`, no `print`, line length).
- `ros_bashrc`: set `ROS_AUTOMATIC_DISCOVERY_RANGE` *before* sourcing ROS. Newer distros default it to SUBNET otherwise.
- `post_build.sh`: relax `set -u` while sourcing colcon's `setup.bash` (it reads unset variables such as `COLCON_TRACE`).
- `install-extensions.sh`: create the profile first. Recent VS Code fails `--install-extension --profile X` with "Profile not found".
- `clang_tidy.sh`: use the runner installed next to the chosen clang-tidy (a runner from another LLVM version fails), fall back to plain clang-tidy.
