<!--
Title: a Conventional Commit, because it becomes the squash-merge commit:
  <type>(<scope>): <summary>    e.g. fix(imu): use sensor timestamp for fusion
Reviewers look at the evidence first and the diff second. The pr-checks job fails if Evidence is
empty or no Risk box is ticked.
-->

## What and why
<!--
Two or three sentences. Link the issue: "Closes #123".
Agents: add "Requested-by: @<person>" naming who asked for the work (CI requires it on bot PRs).
-->

## Evidence
<!--
Proof that it works, not a description of the code. Pick what fits (docs/FEATURE_MAP.md says how
each feature is verified):
- check commands and their results (pre-commit, build, tests), with numbers
- a sim launch, bag replay, HIL or bench run: what you ran and what you observed
- screenshots, plots, scope captures or a short video; before and after for behaviour changes
- firmware: FLASH/RAM usage before and after
-->

## Risk
<!-- Tick exactly one. It decides how much review this needs. -->
- [ ] **Low**: no behaviour change on hardware (docs, tests, tooling, refactor covered by tests)
- [ ] **Medium**: behaviour change verified in sim, replay, host tests or on the bench
- [ ] **High**: touches motion, power, safety, comms with real hardware, or can't be verified off-robot

## Suppressions and rule changes
<!--
List every lint-allow / NOLINT / #[expect] / noqa added, with its reason. Write "none" if none.
If an agent got something wrong while making this change, say how it's now caught
(new lint rule, type, test) or link the agent-mistake issue.
-->
