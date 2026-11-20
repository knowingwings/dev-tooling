"""dev-check: run every check for this project and print a short summary.

One command instead of several, and a summary instead of thousands of lines of tool output: each
step prints one line, failing steps add their first error lines, and the full output goes to
.dev-check/<step>.log. Agents spend their tokens on the failures, not the noise.

Steps come from [[check.step]] tables in patterns.toml:

    [[check.step]]
    name = "clippy"
    run = "cargo clippy --workspace --all-targets -- -D warnings"
    needs = ["cargo"]                  # skipped with a note if a tool is missing
    slow = true                        # skipped by --quick
    summary = 'test result: (.*)'      # regex; matches are shown after PASS/FAIL
    errors = '^(error|warning)'        # regex for the lines shown when it fails
    requires_path = "build-host"       # skipped if this path doesn't exist

`{changed}` in a command expands to the files changed on this branch (against [check] base,
default the remote's default branch, origin/HEAD) plus uncommitted and untracked files. A step whose command uses `{changed}`
is skipped when nothing has changed.

    dev-check              run every step
    dev-check --quick      skip slow steps while iterating
    dev-check --only test  run some steps (comma-separated)
    dev-check --list       show the steps
"""

from __future__ import annotations

import argparse
import re
import shlex
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

DEFAULT_ERRORS = r"(?i)\b(error|fail(ed|ure)?|panicked)\b"
EXCERPT_LINES = 8
LOG_DIR = ".dev-check"


@dataclass
class Step:
    name: str
    run: str
    needs: list[str] = field(default_factory=list)
    slow: bool = False
    summary: str = ""
    errors: str = DEFAULT_ERRORS
    requires_path: str = ""


@dataclass
class Result:
    step: Step
    status: str
    seconds: float = 0.0
    detail: str = ""
    excerpt: list[str] = field(default_factory=list)


def load_steps(root: Path, config: Path | None) -> tuple[list[Step], str]:
    cfg_file = config or root / "patterns.toml"
    if not cfg_file.exists():
        sys.exit(f"dev-check: no {cfg_file.name}; add [[check.step]] tables to it")
    data = tomllib.loads(cfg_file.read_text()).get("check", {})
    fields = Step.__dataclass_fields__
    steps = [Step(**{k: v for k, v in s.items() if k in fields}) for s in data.get("step", [])]
    if not steps:
        sys.exit(f"dev-check: no [[check.step]] tables in {cfg_file.name}")
    return steps, data.get("base", "")


def _git(root: Path, *args: str) -> str:
    git = shutil.which("git")
    if git is None:
        return ""
    p = subprocess.run([git, *args], cwd=root, capture_output=True, text=True, check=False)
    return p.stdout if p.returncode == 0 else ""


def default_base(root: Path) -> str:
    """The remote's default branch (origin/HEAD), else the first of main or master that exists."""
    head = _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").strip()
    if head:
        return head
    for ref in ("origin/main", "origin/master", "main", "master"):
        if _git(root, "rev-parse", "--verify", "--quiet", ref).strip():
            return ref
    return "origin/main"


def changed_files(root: Path, base: str) -> list[str]:
    files: set[str] = set()
    for ref in (base, base.removeprefix("origin/")):
        merge_base = _git(root, "merge-base", ref, "HEAD").strip()
        if merge_base:
            files.update(
                _git(root, "diff", "--name-only", "--diff-filter=d", merge_base).splitlines()
            )
            break
    files.update(_git(root, "diff", "--name-only", "--diff-filter=d", "HEAD").splitlines())
    files.update(_git(root, "ls-files", "--others", "--exclude-standard").splitlines())
    own_logs = f"{LOG_DIR}/"
    return sorted(f for f in files if (root / f).is_file() and not f.startswith(own_logs))


def _shell() -> list[str]:
    bash = shutil.which("bash")
    return [bash, "-c"] if bash else ["/bin/sh", "-c"]


def run_step(step: Step, root: Path, changed: list[str]) -> Result:
    missing = [t for t in step.needs if shutil.which(t) is None]
    if missing:
        return Result(step, "SKIP", detail=f"needs {', '.join(missing)} (not installed)")
    if step.requires_path and not (root / step.requires_path).exists():
        return Result(step, "SKIP", detail=f"{step.requires_path} not found")
    cmd = step.run
    if "{changed}" in cmd:
        if not changed:
            return Result(step, "SKIP", detail="nothing changed")
        cmd = cmd.replace("{changed}", " ".join(shlex.quote(f) for f in changed))

    start = time.monotonic()
    p = subprocess.run(
        [*_shell(), cmd], cwd=root, capture_output=True, text=True, errors="replace", check=False
    )
    seconds = time.monotonic() - start
    output = p.stdout + p.stderr
    log = root / LOG_DIR / f"{step.name}.log"
    log.parent.mkdir(exist_ok=True)
    log.write_text(f"$ {step.run}\n\n{output}")

    detail = ""
    if step.summary:
        found = re.findall(step.summary, output, re.M)
        detail = " | ".join(f if isinstance(f, str) else " ".join(f) for f in found).strip()
    if p.returncode == 0:
        return Result(step, "PASS", seconds, detail)
    lines = [ln.rstrip() for ln in output.splitlines() if re.search(step.errors, ln)]
    if not detail:
        detail = f"{len(lines)} error line(s)" if lines else f"exit code {p.returncode}"
    excerpt = lines[:EXCERPT_LINES] or output.strip().splitlines()[-EXCERPT_LINES:]
    if len(lines) > EXCERPT_LINES:
        excerpt.append(f"... {len(lines) - EXCERPT_LINES} more")
    excerpt.append(f"full log: {log.relative_to(root)}")
    return Result(step, "FAIL", seconds, detail, excerpt)


def report(result: Result) -> None:
    timing = f"{result.seconds:5.1f}s" if result.status != "SKIP" else "      "
    line = f"{result.status}  {result.step.name:<14} {timing}  {result.detail}".rstrip()
    sys.stdout.write(line + "\n")
    for excerpt in result.excerpt:
        sys.stdout.write(f"      {excerpt}\n")
    sys.stdout.flush()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--quick", action="store_true", help="skip slow steps")
    ap.add_argument("--only", default="", help="comma-separated step names")
    ap.add_argument("--list", action="store_true", help="list the steps and exit")
    ap.add_argument("--config", type=Path, default=None)
    args = ap.parse_args()

    root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip() or Path.cwd())
    steps, base = load_steps(root, args.config)
    if args.list:
        for s in steps:
            sys.stdout.write(f"{s.name:<14} {'(slow) ' if s.slow else ''}{s.run}\n")
        return 0
    only = {n.strip() for n in args.only.split(",") if n.strip()}
    unknown = only - {s.name for s in steps}
    if unknown:
        sys.exit(f"dev-check: unknown step(s): {', '.join(sorted(unknown))} (see --list)")

    changed = changed_files(root, base or default_base(root))
    results: list[Result] = []
    for step in steps:
        if only and step.name not in only:
            continue
        if args.quick and step.slow and not only:
            result = Result(step, "SKIP", detail="slow (--quick)")
        else:
            result = run_step(step, root, changed)
        results.append(result)
        report(result)

    counts = {s: sum(r.status == s for r in results) for s in ("PASS", "FAIL", "SKIP")}
    sys.stdout.write(
        f"\n{counts['PASS']} passed, {counts['FAIL']} failed, {counts['SKIP']} skipped"
        f"  (logs in {LOG_DIR}/)\n"
    )
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
