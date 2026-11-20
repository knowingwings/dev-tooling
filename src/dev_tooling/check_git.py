"""Git and PR conventions, enforced instead of written down.

check-branch (pre-push): branch names follow `<type>/<short-description>` (or an agent prefix
such as `claude/...`), and nothing is pushed straight to a protected branch.

check-pr (CI on pull requests): the title is a Conventional Commit (it becomes the squash-merge
commit), the body's Evidence section is filled in and one Risk box is ticked, and changes to the
checks themselves (lint configs, AGENTS.md, CI) aren't mixed with other code changes. A PR that
adopts or updates the kit (it changes `.dev-tooling-version`) is the exception: it has to change the
checks and the files they need together, and the owner reviews it because the file is protected.

check-automerge (CI): whether a PR may merge itself once its checks pass. Only Low risk, approved
by someone other than the author, not touching the checks themselves, and not labelled to hold.

Configured by an optional [git] table in patterns.toml.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

DEFAULTS: dict[str, object] = {
    "branch_types": [
        "feat",
        "feature",
        "fix",
        "docs",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
        "hotfix",
        "release",
    ],
    "agent_prefixes": ["claude", "cursor", "codex", "copilot", "agent", "dependabot", "renovate"],
    "protected_branches": ["main", "master"],
    "title_types": [
        "feat",
        "fix",
        "docs",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
    ],
    "title_max_length": 72,
    "require_evidence": True,
    "require_risk": True,
    "require_requested_by_for_bots": True,
    "bots_exempt_from_requested_by": ["dependabot[bot]", "renovate[bot]"],
    "automerge": False,
    "automerge_risk": ["Low"],
    "automerge_require_approval": True,
    "automerge_block_labels": ["do-not-merge", "needs-human", "hold"],
    "protected_paths": [
        ".github/**",
        "AGENTS.md",
        "CLAUDE.md",
        ".claude/**",
        "docs/agents/**",
        ".pre-commit-config.yaml",
        "patterns.toml",
        ".clang-tidy",
        ".clang-format",
        ".clangd",
        "ruff.toml",
        "clippy.toml",
        "rustfmt.toml",
        "rust-toolchain.toml",
        "cmake/warnings.cmake",
        ".typst-version",
        ".dev-tooling-version",
    ],
}

KIT_VERSION_FILE = ".dev-tooling-version"


@dataclass
class GitConfig:
    branch_types: list[str] = field(default_factory=list)
    agent_prefixes: list[str] = field(default_factory=list)
    protected_branches: list[str] = field(default_factory=list)
    title_types: list[str] = field(default_factory=list)
    title_max_length: int = 72
    require_evidence: bool = True
    require_risk: bool = True
    protected_paths: list[str] = field(default_factory=list)
    require_requested_by_for_bots: bool = True
    bots_exempt_from_requested_by: list[str] = field(default_factory=list)
    automerge: bool = False
    automerge_risk: list[str] = field(default_factory=list)
    automerge_require_approval: bool = True
    automerge_block_labels: list[str] = field(default_factory=list)


def load_config(root: Path, path: Path | None = None) -> GitConfig:
    data: dict[str, object] = dict(DEFAULTS)
    cfg_file = path or root / "patterns.toml"
    if cfg_file.exists():
        data.update(tomllib.loads(cfg_file.read_text()).get("git", {}))
    return GitConfig(**{k: data[k] for k in GitConfig.__dataclass_fields__ if k in data})


def branch_problem(name: str, cfg: GitConfig) -> str | None:
    """Why this branch name breaks the convention, or None if it's fine."""
    if name in cfg.protected_branches:
        return (
            f"'{name}' is protected: don't push to it directly. Create a branch "
            "(git switch -c feat/<short-description>) and open a pull request."
        )
    types = "|".join(map(re.escape, cfg.branch_types))
    agents = "|".join(map(re.escape, cfg.agent_prefixes))
    if re.fullmatch(rf"({types})/(\d+-)?[a-z0-9][a-z0-9._-]*", name):
        return None
    if agents and re.fullmatch(rf"({agents})/[\w./-]+", name):
        return None
    return (
        f"Branch '{name}' doesn't follow <type>/<short-description> in lowercase-with-dashes, "
        "e.g. feat/motor-current-limit or fix/123-imu-timestamp. "
        f"Types: {', '.join(cfg.branch_types)}. Rename it with: git branch -m <new-name>"
    )


def title_problem(title: str, cfg: GitConfig) -> str | None:
    types = "|".join(map(re.escape, cfg.title_types))
    if not re.fullmatch(rf"({types})(\([a-z0-9._/-]+\))?!?: \S.*", title.strip()):
        return (
            "PR title must be a Conventional Commit, because it becomes the squash-merge commit: "
            "<type>(<optional scope>): <summary>, "
            "e.g. 'fix(imu): use sensor timestamp for fusion'. "
            f"Types: {', '.join(cfg.title_types)}. Add ! after the type for breaking changes."
        )
    if len(title.strip()) > cfg.title_max_length:
        return f"PR title is {len(title.strip())} characters; keep it to {cfg.title_max_length}."
    return None


def _section(body: str, heading: str) -> str | None:
    m = re.search(rf"^##\s+{re.escape(heading)}\b[^\n]*\n(.*?)(?=^##\s|\Z)", body, re.M | re.S)
    return m.group(1) if m else None


def body_problems(body: str, cfg: GitConfig, author: str = "") -> list[str]:
    clean = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    problems: list[str] = []
    is_agent = author.endswith("[bot]") and author not in cfg.bots_exempt_from_requested_by
    if (
        cfg.require_requested_by_for_bots
        and is_agent
        and not re.search(r"Requested-by: @\w", clean)
    ):
        problems.append(
            f"This PR was opened by {author}, so add 'Requested-by: @<person>' to the body: the "
            "person who asked for the work, so ownership stays visible."
        )
    if cfg.require_evidence:
        evidence = _section(clean, "Evidence")
        if evidence is None or not re.search(r"\w", evidence):
            problems.append(
                "The Evidence section is empty. Show it works: the check commands and their "
                "results, test output, a sim/bag/bench run, or a screenshot, plot or video "
                "(before and after for behaviour changes). See docs/FEATURE_MAP.md for how each "
                "feature is verified."
            )
    if cfg.require_risk:
        risk = _section(clean, "Risk")
        ticked = len(re.findall(r"^\s*[-*] \[[xX]\]", risk or "", re.M))
        if ticked != 1:
            problems.append(
                f"Tick exactly one box in the Risk section (found {ticked}): it decides how much "
                "review the PR needs."
            )
    return problems


def ticked_risk(body: str) -> list[str]:
    clean = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    risk = _section(clean, "Risk") or ""
    return re.findall(r"^\s*[-*] \[[xX]\]\s*\*\*(\w+)\*\*", risk, re.M)


def approval_state(reviews: list[dict[str, object]], author: str) -> tuple[bool, list[str]]:
    """(approved by a non-author, reviewers whose latest review requests changes)."""
    latest: dict[str, str] = {}
    for r in reviews:
        user = str((r.get("user") or {}).get("login", ""))  # type: ignore[union-attr]
        state = str(r.get("state", ""))
        if user and user != author and state in {"APPROVED", "CHANGES_REQUESTED", "DISMISSED"}:
            latest[user] = state
    approved = any(s == "APPROVED" for s in latest.values())
    blocking = sorted(u for u, s in latest.items() if s == "CHANGES_REQUESTED")
    return approved, blocking


def automerge_reasons(
    body: str,
    labels: list[str],
    changed: list[str],
    reviews: list[dict[str, object]],
    author: str,
    cfg: GitConfig,
) -> list[str]:
    """Why this PR must not merge itself; empty means it may."""
    if not cfg.automerge:
        return ["auto-merge is off for this repo ([git] automerge = false in patterns.toml)"]
    reasons: list[str] = []
    risk = ticked_risk(body)
    if len(risk) != 1 or risk[0] not in cfg.automerge_risk:
        shown = risk[0] if len(risk) == 1 else "not set"
        reasons.append(f"risk is {shown}; only {', '.join(cfg.automerge_risk)} merges itself")
    held = sorted(set(labels) & set(cfg.automerge_block_labels))
    if held:
        reasons.append(f"labelled {', '.join(held)}")
    touched = [p for p in changed if any(fnmatch.fnmatch(p, g) for g in cfg.protected_paths)]
    if touched:
        reasons.append(
            f"changes the checks themselves ({', '.join(touched[:3])}): a human reviews those"
        )
    approved, blocking = approval_state(reviews, author)
    if blocking:
        reasons.append(f"changes requested by {', '.join(blocking)}")
    elif cfg.automerge_require_approval and not approved:
        reasons.append("no approval yet from anyone other than the author")
    return reasons


def mixed_change_problem(changed: list[str], cfg: GitConfig) -> str | None:
    """A problem when checks and other code change together, except in a kit adoption or update."""

    def protected(p: str) -> bool:
        return any(fnmatch.fnmatch(p, g) for g in cfg.protected_paths)

    if KIT_VERSION_FILE in changed:
        return None
    env = [p for p in changed if protected(p)]
    other = [p for p in changed if not protected(p)]
    if env and other:
        shown = ", ".join(env[:5]) + (" ..." if len(env) > 5 else "")
        return (
            f"This PR changes the checks or agent instructions ({shown}) together with other code. "
            "Put those changes in their own PR (e.g. 'chore(lint): ...') so they're reviewed "
            "on their own and can't quietly loosen the checks this change is judged by."
        )
    return None


def _git(*args: str, cwd: Path) -> str:
    git = shutil.which("git")
    if git is None:
        sys.exit("check_git: git not found on PATH")
    return subprocess.run(
        [git, *args], cwd=cwd, capture_output=True, text=True, check=False
    ).stdout.strip()


def main_branch() -> int:
    ap = argparse.ArgumentParser(
        description="Check the branch name and block pushes to protected branches."
    )
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--branch", default=None, help="branch to check (default: the current branch)")
    args = ap.parse_args()
    root = Path.cwd()
    cfg = load_config(root, args.config)

    names = []
    remote = os.environ.get("PRE_COMMIT_REMOTE_BRANCH", "")
    if remote.startswith("refs/heads/"):
        names.append(remote.removeprefix("refs/heads/"))
    local = args.branch or _git("rev-parse", "--abbrev-ref", "HEAD", cwd=root)
    if local and local != "HEAD":
        names.append(local)

    for name in dict.fromkeys(names):
        problem = branch_problem(name, cfg)
        if problem:
            sys.stdout.write(f"[branch-name] {problem}\n")
            return 1
    return 0


def main_pr() -> int:
    ap = argparse.ArgumentParser(
        description="Check a pull request's title, body and changed files."
    )
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--title", default=os.environ.get("PR_TITLE", ""))
    ap.add_argument("--body", default=os.environ.get("PR_BODY", ""))
    ap.add_argument("--branch", default=os.environ.get("PR_HEAD_REF", ""))
    ap.add_argument(
        "--base", default=os.environ.get("PR_BASE_REF", ""), help="diff against origin/<base>"
    )
    ap.add_argument("--author", default=os.environ.get("PR_AUTHOR", ""))
    args = ap.parse_args()
    root = Path.cwd()
    cfg = load_config(root, args.config)

    problems: list[tuple[str, str]] = []
    if args.branch and (p := branch_problem(args.branch, cfg)):
        problems.append(("branch-name", p))
    if p := title_problem(args.title, cfg):
        problems.append(("pr-title", p))
    problems += [("pr-body", p) for p in body_problems(args.body, cfg, args.author)]
    if args.base:
        changed = _git("diff", "--name-only", f"origin/{args.base}...HEAD", cwd=root).splitlines()
        if p := mixed_change_problem(changed, cfg):
            problems.append(("mixed-change", p))

    for rule, msg in problems:
        sys.stdout.write(f"[{rule}] {msg}\n")
    return 1 if problems else 0


def main_automerge() -> int:
    ap = argparse.ArgumentParser(description="Decide whether a PR may merge itself once green.")
    ap.add_argument("--config", type=Path, default=None)
    args = ap.parse_args()
    root = Path.cwd()
    cfg = load_config(root, args.config)
    base = os.environ.get("PR_BASE_REF", "")
    changed = (
        _git("diff", "--name-only", f"origin/{base}...HEAD", cwd=root).splitlines() if base else []
    )
    labels = [x for x in os.environ.get("PR_LABELS", "").split(",") if x]
    reviews = json.loads(os.environ.get("PR_REVIEWS_JSON") or "[]")
    reasons = automerge_reasons(
        os.environ.get("PR_BODY", ""),
        labels,
        changed,
        reviews,
        os.environ.get("PR_AUTHOR", ""),
        cfg,
    )
    if reasons:
        sys.stdout.write("not eligible for auto-merge:\n" + "".join(f"  - {r}\n" for r in reasons))
        return 1
    sys.stdout.write("eligible for auto-merge: merges when every required check passes\n")
    return 0


if __name__ == "__main__":
    sys.exit(main_pr())
