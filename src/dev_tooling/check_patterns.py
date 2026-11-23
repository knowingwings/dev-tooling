#!/usr/bin/env python3
"""Path-scoped banned-pattern checker with fix-it messages.

Handles the rules that compilers, clang-tidy and ruff can't express easily:
"X is only allowed in these directories", project conventions, etc.

Rules live in patterns.toml at the repo root (or pass --config). Each rule:

    [[rule]]
    id      = "fw-register-access-outside-bsp"
    pattern = '\\bGPIO[A-K]\\s*->'            # Python regex, matched per line
    include = ["**/*.c", "**/*.h"]          # globs, relative to repo root
    exclude = ["bsp/**", "drivers/**"]      # optional
    message = "Tell the reader (human or agent) HOW to fix it, not just what's wrong."

A rule with `multiline = true` is matched against the whole file (re.MULTILINE), for code that
a formatter splits over several lines, such as a loop body that clang-format moves to the next
line. Its hit, and its lint-allow, belong to the line where the match starts.

Suppression (must name the rule AND give a reason, on the same or previous line):

    // lint-allow(fw-no-blocking-delay): clock tree not up yet, timers unavailable

Usage:
    check_patterns.py [files...]     # pre-commit passes changed files
    check_patterns.py                # no args: every git-tracked file
"""

from __future__ import annotations

import argparse
import fnmatch
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # type: ignore[no-redef]
    except ModuleNotFoundError:
        sys.exit("check_patterns: needs Python 3.11+, or `pip install tomli` on 3.10")

ALLOW_RE = re.compile(r"lint-allow\(([\w,\s-]+)\):\s*(.+)")
MIN_REASON_LEN = 10
COMMENT_PREFIXES = ("//", "#", "*", "/*")


@dataclass
class Rule:
    id: str
    pattern: re.Pattern[str]
    message: str
    include: list[str]
    exclude: list[str]
    multiline: bool = False

    def applies_to(self, rel: str) -> bool:
        return _match_any(rel, self.include) and not _match_any(rel, self.exclude)


def _glob_variants(g: str) -> set[str]:
    """'**/' means zero or more directories; fnmatch's '*' already crosses '/',
    so also try every combination with each '**/' removed."""
    variants = {g}
    while True:
        new = {
            v[:i] + v[i + 3 :] for v in variants for i in range(len(v)) if v.startswith("**/", i)
        }
        if new <= variants:
            return variants
        variants |= new


def _match_any(rel: str, globs: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, v) for g in globs for v in _glob_variants(g))


def load_rules(config: Path) -> list[Rule]:
    data = tomllib.loads(config.read_text())
    return [
        Rule(
            id=r["id"],
            pattern=re.compile(r["pattern"], re.MULTILINE if r.get("multiline") else 0),
            message=r["message"].strip(),
            include=r.get("include", ["**/*"]),
            exclude=r.get("exclude", []),
            multiline=bool(r.get("multiline", False)),
        )
        for r in data.get("rule", [])
    ]


def find_hits(lines: list[str], rules: list[Rule]) -> list[tuple[int, int, Rule]]:
    """Return (line index, column, rule) for every match, in file order.

    Line rules skip comment lines. A multiline rule is matched against the whole file, and a
    match is dropped when the line it starts on is a comment.
    """
    hits = [
        (i, m.start(), rule)
        for i, line in enumerate(lines)
        if not line.lstrip().startswith(COMMENT_PREFIXES)
        for rule in rules
        if not rule.multiline and (m := rule.pattern.search(line))
    ]
    text = "\n".join(lines)
    for rule in (r for r in rules if r.multiline):
        starts = (m.start() for m in rule.pattern.finditer(text))
        located = ((text.count("\n", 0, s), s - (text.rfind("\n", 0, s) + 1)) for s in starts)
        hits.extend(
            (i, col, rule)
            for i, col in located
            if not lines[i].lstrip().startswith(COMMENT_PREFIXES)
        )
    return sorted(hits, key=lambda h: (h[0], h[1]))


def allowed(lines: list[str], idx: int, rule_id: str) -> tuple[bool, str | None]:
    """Return (suppressed, problem). problem is set when a suppression lacks a reason."""
    for j in (idx, idx - 1):
        if j < 0:
            continue
        m = ALLOW_RE.search(lines[j])
        if m and rule_id in [s.strip() for s in m.group(1).split(",")]:
            if len(m.group(2).strip()) < MIN_REASON_LEN:
                return False, "lint-allow needs a real reason a reviewer would accept"
            return True, None
    return False, None


def tracked_files(root: Path) -> list[str]:
    git = shutil.which("git")
    if git is None:
        sys.exit("check_patterns: git not found on PATH (needed to list tracked files)")
    out = subprocess.run([git, "ls-files"], cwd=root, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files", nargs="*")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    args = ap.parse_args()

    root = args.root.resolve()
    config = args.config or root / "patterns.toml"
    if not config.exists():
        sys.stderr.write(f"check_patterns: no config at {config}\n")
        return 2
    rules = load_rules(config)

    files = args.files or tracked_files(root)
    failures = 0
    for f in files:
        path = (root / f) if not Path(f).is_absolute() else Path(f)
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = Path(f).as_posix()
        active = [r for r in rules if r.applies_to(rel)]
        if not active or not path.is_file():
            continue
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for i, col, rule in find_hits(lines, active):
            ok, problem = allowed(lines, i, rule.id)
            if ok:
                continue
            msg = problem or rule.message
            sys.stdout.write(f"{rel}:{i + 1}:{col + 1}: [{rule.id}] {msg}\n")
            failures += 1

    if failures:
        sys.stderr.write(
            f"\n{failures} pattern violation(s). Fix the root cause; only add "
            "`lint-allow(<rule-id>): <reason>` if the rule genuinely doesn't apply.\n"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
