"""Git and PR conventions, enforced instead of written down.

check-branch (pre-push): branch names follow `<type>/<short-description>` (or an agent prefix
such as `claude/...`), and nothing is pushed straight to a protected branch.

check-pr (CI on pull requests): the title is a Conventional Commit (it becomes the squash-merge
commit), the body's Evidence section is filled in and one Risk box is ticked, and changes to the
checks themselves (lint configs, AGENTS.md, CI) aren't mixed with other code changes.

Configured by an optional [git] table in patterns.toml.
"""

from __future__ import annotations

import argparse
import fnmatch
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
    "protected_paths": [
        ".github/**",
        "AGENTS.md",
        "CLAUDE.md",
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
    ],
}


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


def body_problems(body: str, cfg: GitConfig) -> list[str]:
    clean = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    problems: list[str] = []
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


def mixed_change_problem(changed: list[str], cfg: GitConfig) -> str | None:
    def protected(p: str) -> bool:
        return any(fnmatch.fnmatch(p, g) for g in cfg.protected_paths)

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
    args = ap.parse_args()
    root = Path.cwd()
    cfg = load_config(root, args.config)

    problems: list[tuple[str, str]] = []
    if args.branch and (p := branch_problem(args.branch, cfg)):
        problems.append(("branch-name", p))
    if p := title_problem(args.title, cfg):
        problems.append(("pr-title", p))
    problems += [("pr-body", p) for p in body_problems(args.body, cfg)]
    if args.base:
        changed = _git("diff", "--name-only", f"origin/{args.base}...HEAD", cwd=root).splitlines()
        if p := mixed_change_problem(changed, cfg):
            problems.append(("mixed-change", p))

    for rule, msg in problems:
        sys.stdout.write(f"[{rule}] {msg}\n")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main_pr())
