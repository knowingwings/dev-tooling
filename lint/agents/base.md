# Working in this repo

These instructions are for any coding agent (Claude Code, Cursor, Codex...) and for people.
Shared rules come first; the section for this repo's stack follows.

## Before you say a change is done
- Run every check listed for this stack below and put a short summary of each result in your final
  message: the command, pass/fail, and any numbers it reports. Evidence first, then the diff.
- If a check fails and you can't fix it, say so plainly. Don't claim it passed.

## Lint and checks
- Every lint message says how to fix the problem. Fix the root cause.
- Never edit lint, compiler-warning or type-checker config to get a check passing.
- A suppression (`lint-allow(<rule>): <reason>`, `NOLINT`, `#[expect(.., reason)]`, `noqa`) is only for
  cases where the rule genuinely doesn't apply. Give a reason a reviewer would accept, and list every
  suppression you added in your summary.

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

## Git
- Work on a branch. Don't commit to main, force-push, or push without being asked.
