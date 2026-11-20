# Working in this repo

These instructions are for any coding agent (Claude Code, Cursor, Codex...) and for people.
Shared rules come first; the section for this repo's stack follows.

## Before you say a change is done
- Run `./check` (every check for this stack, one summary line each) and put its summary in your final
  message and the PR's Evidence section. Evidence first, then the diff.
- If a check fails and you can't fix it, say so plainly. Don't claim it passed.

## Verification
Reviewers judge the evidence, not the diff, so most of your effort goes into proving the change works.
- `docs/FEATURE_MAP.md` lists every behaviour and how to verify it. Run the checks for every feature
  your change touches, and add a row when you add a feature.
- Prefer evidence a machine produced: test output, a sim launch or bag replay with what you observed,
  a plot, a screenshot or recording. For behaviour changes, show before and after.
- If something can only be verified on real hardware, say exactly what a person needs to run and
  mark the PR **High** risk (see Hardware safety).

## Lint and checks
- Every lint message says how to fix the problem. Fix the root cause.
- Never edit lint, compiler-warning or type-checker config to get a check passing.
- A suppression (`lint-allow(<rule>): <reason>`, `NOLINT`, `#[expect(.., reason)]`, `noqa`) is only for
  cases where the rule genuinely doesn't apply. Give a reason a reviewer would accept, and list every
  suppression you added in your summary.

## When you're corrected
A correction should become a check, not another line here. If you're told you did something wrong,
propose the deterministic fix: a lint rule, a `patterns.toml` rule, a type or API that makes the
mistake impossible, or a test. If it can't be done in this change, open an issue with the
**Agent mistake → check** template.

## Comments
New comments are blocked by the `check-comments` hook, because they go stale and get used to justify
workarounds. Say it somewhere a tool checks instead:
- a clearer function or variable name, or a smaller function
- a type, enum, assert or `static_assert` that makes the wrong thing impossible
- a test that pins the behaviour
- the commit message, for the why behind a change

Allowed: doc comments on public API (`///`, `//!`, `/** */`, docstrings), `SAFETY:` on unsafe blocks,
`REF(<datasheet section, erratum id or issue URL>): <fact>` for hardware facts code can't express,
suppressions with a reason, and licence headers.

## Hardware safety
Never flash a board, change option bytes or fuses, open a serial/CAN port to a device, or run anything
that commands real actuators (motors, arms, grippers), unless the person you're working for asks in
this session. Verify with simulation, bag replay, host tests or fakes instead.

## Agent roles
Work is split between four roles, each a GitHub App owned by the repo owner, so every PR, review and
commit shows which role did it. Each role's full instructions are in `docs/agents/<role>.md` (Claude Code
also has them as subagents in `.claude/agents/`).
- **architect**: goals → Task issues with acceptance criteria and proof expected; keeps the feature map
  current. No production code.
- **builder**: one Task per branch → PR with evidence. Never approves or merges.
- **reviewer**: fresh eyes. Re-runs `./check` and the feature-map checks, judges evidence and Risk,
  approves or requests changes. Never edits code.
- **publisher**: low-risk approved PRs merge themselves; summarises Medium/High for the owner; releases;
  turns repeated review findings into Agent mistake → check issues.

Run GitHub-facing commands as your role: `as-agent <role> git push ...`, `as-agent <role> gh pr ...`.
Commits made through `as-agent` carry the owner as `Co-authored-by`, and bot PRs must include
`Requested-by: @<person>`. If `as-agent` isn't set up, say so and work as the person you're helping.

## Git and pull requests
These are checked by hooks and CI, so getting them right first time saves a round trip.
- **Branch:** `<type>/<short-description>` in lowercase-with-dashes, optionally with the issue number:
  `feat/motor-current-limit`, `fix/123-imu-timestamp`. Types: feat, fix, docs, refactor, perf, test,
  build, ci, chore, revert. Never commit or push to `main`; never force-push a shared branch.
- **Commits:** small and focused, with a message that explains why. Don't push without being asked.
- **PR title:** a Conventional Commit, since it becomes the squash-merge commit:
  `fix(imu): use sensor timestamp for fusion`. Add `!` after the type for breaking changes.
- **PR body:** fill in the template. **Evidence** must show it works, and exactly one **Risk** box is
  ticked. List every suppression you added.
- **Changes to the checks themselves** (lint configs, `patterns.toml`, `AGENTS.md`, `.github/`, hooks)
  go in their own PR, never mixed with feature work. CI rejects mixed PRs.
