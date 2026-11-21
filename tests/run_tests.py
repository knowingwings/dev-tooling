#!/usr/bin/env python3
"""Self-test for dev-tooling: run every profile's tools against deliberately bad fixtures and
compare the rule hits with tests/expected/<profile>.txt.

    python3 tests/run_tests.py                 # all profiles; tools missing locally are skipped
    python3 tests/run_tests.py ros2 rust       # just these
    python3 tests/run_tests.py --strict        # a missing tool is a failure (CI)
    python3 tests/run_tests.py --update        # rewrite expected files from current output

After --update, review `git diff tests/expected/`: every changed count is a rule that
changed behaviour. Adding a rule = add a bad line to tests/fixtures/<profile>/, run --update,
check the diff.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent
FIX = KIT / "tests" / "fixtures"
EXP = KIT / "tests" / "expected"
LINT = KIT / "lint"
ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class SkipError(Exception):
    pass


def need(tool: str) -> None:
    if shutil.which(tool) is None:
        raise SkipError(f"{tool} not on PATH")


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    p = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False, env={**os.environ, **(env or {})}
    )
    return p.stdout + p.stderr


def git_init(d: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=d, check=True)
    subprocess.run(["git", "add", "-A"], cwd=d, check=True)


# ---- per-tool parsers: output -> Counter of "tool:rule" -----------------------------------


def patterns(d: Path) -> Counter[str]:
    out = run(
        [sys.executable, "-m", "dev_tooling.check_patterns"],
        d,
        env={"PYTHONPATH": str(KIT / "src")},
    )
    hits = Counter(f"patterns:{m}" for m in re.findall(r": \[([\w-]+)\] ", out))
    hits.update(
        f"patterns:{m.split()[0]}-no-reason"
        for m in re.findall(r": \[([\w-]+)\] lint-allow needs", out)
    )
    for k in list(hits):  # a no-reason line also matched the generic pattern above
        if k.endswith("-no-reason"):
            hits[k.removesuffix("-no-reason")] -= hits[k]
    return +hits


def comments(d: Path) -> Counter[str]:
    out = run(
        [sys.executable, "-m", "dev_tooling.check_comments"],
        d,
        env={"PYTHONPATH": str(KIT / "src")},
    )
    return Counter(f"comments:{m}" for m in re.findall(r": \[(no-comments[\w-]*)\] ", out))


def ruff(d: Path, config: Path, paths: list[str]) -> Counter[str]:
    need("ruff")
    out = run(
        [
            "ruff",
            "check",
            "--no-cache",
            "--config",
            str(config),
            "--output-format",
            "concise",
            *paths,
        ],
        d,
    )
    return Counter(f"ruff:{m}" for m in re.findall(r"^\S+:\d+:\d+: ([A-Z]+\d+) ", out, re.M))


def clang_tidy(d: Path, files: list[str], std: str, host_target: bool = False) -> Counter[str]:
    need("clang-tidy")
    if host_target:  # fixtures don't need the arm sysroot: analyse for the host instead
        cfg = d / ".clang-tidy"
        cfg.write_text(
            cfg.read_text().replace("--target=arm-none-eabi", "--target=x86_64-linux-gnu")
        )
    hits: Counter[str] = Counter()
    for f in files:
        out = run(["clang-tidy", "--quiet", f, "--", f"-std={std}"], d)
        hits.update(
            f"clang-tidy:{m}"
            for m in re.findall(r"(?:error|warning): .* \[([\w.-]+)(?:,[^\]]*)?\]$", out, re.M)
        )
    return hits


def clippy(d: Path) -> Counter[str]:
    need("cargo")
    out = run(["cargo", "clippy", "--quiet", "--all-targets", "--message-format=json"], d)
    seen: set[tuple[str, str, int]] = set()  # --all-targets reports each hit once per target
    for line in out.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = msg.get("message") or {}
        code = (m.get("code") or {}).get("code")
        if msg.get("reason") != "compiler-message" or not code:
            continue
        span = next((s for s in m.get("spans", []) if s.get("is_primary")), {})
        seen.add((code, span.get("file_name", ""), span.get("line_start", 0)))
    return Counter(
        f"clippy:{c.removeprefix('clippy::')}" if c.startswith("clippy::") else f"rustc:{c}"
        for c, _, _ in seen
    )


def pyright(d: Path) -> Counter[str]:
    need("uv")
    out = run(["uv", "run", "--quiet", "pyright", "--outputjson"], d)
    try:
        diags = json.loads(out[out.index("{") :])["generalDiagnostics"]
    except (ValueError, KeyError) as e:
        raise SkipError(f"pyright output unreadable: {e}") from e
    return Counter(f"pyright:{x.get('rule', x['severity'])}" for x in diags)


def pytest_summary(d: Path) -> Counter[str]:
    out = run(["uv", "run", "--quiet", "pytest", "-q", "-p", "no:cacheprovider"], d)
    hits: Counter[str] = Counter()
    for n, what in re.findall(r"(\d+) (passed|failed|deselected|error)", out):
        hits[f"pytest:{what}"] = int(n)
    return hits


# ---- profiles ------------------------------------------------------------------------------


def prof_ros2(d: Path) -> Counter[str]:
    for f in (".clang-tidy", "patterns.toml", "ruff.toml"):
        shutil.copy(LINT / "ros2" / f, d)
    git_init(d)
    return (
        patterns(d)
        + comments(d)
        + ruff(d, d / "ruff.toml", ["my_pkg"])
        + clang_tidy(d, ["my_pkg/src/bad_node.cpp"], "c++17")
    )


def prof_firmware(d: Path) -> Counter[str]:
    for f in (".clang-tidy", "patterns.toml"):
        shutil.copy(LINT / "firmware" / f, d)
    git_init(d)
    return patterns(d) + comments(d) + clang_tidy(d, ["app/motor.c"], "c11", host_target=True)


def prof_rust(d: Path) -> Counter[str]:
    for f in ("clippy.toml", "rustfmt.toml", "patterns.toml"):
        shutil.copy(LINT / "rust" / f, d)
    (d / "Cargo.toml").write_text(
        '[workspace]\nmembers = ["crates/app"]\nresolver = "3"\n\n'
        + (LINT / "rust" / "Cargo-lints.toml").read_text()
    )
    git_init(d)
    return patterns(d) + comments(d) + clippy(d)


def prof_python(d: Path) -> Counter[str]:
    shutil.copy(LINT / "python" / "pyproject.toml", d)
    shutil.copy(LINT / "python" / "patterns.toml", d)
    git_init(d)
    hits = comments(d) + ruff(d, d / "pyproject.toml", ["."])
    need("uv")
    subprocess.run(["uv", "sync", "--quiet"], cwd=d, check=True)
    return hits + pyright(d) + pytest_summary(d)


def typst_compile(d: Path) -> Counter[str]:
    need("typst")
    out = run(["bash", str(KIT / "lint" / "shared" / "typst_compile.sh")], d)
    hits: Counter[str] = Counter()
    hits["typst:ok"] = len(re.findall(r"^ok  ", out, re.M))
    hits["typst:error"] = len(re.findall(r"^error: ", out, re.M))
    hits["typst:warning"] = len(re.findall(r"^warning: ", out, re.M))
    hits["typst:font-not-reproducible"] = len(re.findall(r"^FAIL .*uses a font", out, re.M))
    return +hits


def typstyle(d: Path) -> Counter[str]:
    need("typstyle")
    files = sorted(str(p.relative_to(d)) for p in d.rglob("*.typ"))
    hits: Counter[str] = Counter()
    for f in files:
        p = subprocess.run(["typstyle", "--check", f], cwd=d, capture_output=True, check=False)
        hits["typstyle:needs-format"] += p.returncode != 0
    return +hits


def prof_typst(d: Path) -> Counter[str]:
    shutil.copy(LINT / "typst" / ".typst-version", d)
    git_init(d)
    return typst_compile(d) + typstyle(d)


def eslint(d: Path) -> Counter[str]:
    out = run(["npx", "--no-install", "eslint", "-f", "json", "."], d)
    hits: Counter[str] = Counter()
    for f in json.loads(out[out.index("[") :]):
        for m in f["messages"]:
            hits[f"eslint:{m['ruleId']}"] += 1
    return hits


def prettier(d: Path) -> Counter[str]:
    p = subprocess.run(
        ["npx", "--no-install", "prettier", "--check", "."],
        cwd=d,
        capture_output=True,
        text=True,
        check=False,
    )
    out = ANSI.sub("", p.stdout + p.stderr)
    if p.returncode not in (0, 1) or re.search(r"^\[error\]", out, re.M):
        raise RuntimeError(f"prettier failed (exit {p.returncode}):\n{out}")
    return Counter(
        {"prettier:unformatted": len(re.findall(r"^\[warn\] (?!Code style)", out, re.M))}
    )


def prof_astro(d: Path) -> Counter[str]:
    for name in ("eslint.config.mjs", ".prettierrc.json", ".prettierignore", "patterns.toml"):
        shutil.copy(LINT / "astro" / name, d)
    need("npm")
    subprocess.run(
        ["npm", "install", "--ignore-scripts", "--no-audit", "--no-fund", "--silent"],
        cwd=d,
        check=True,
    )
    git_init(d)
    return patterns(d) + eslint(d) + prettier(d)


PROFILES = {
    "ros2": prof_ros2,
    "firmware": prof_firmware,
    "rust": prof_rust,
    "python": prof_python,
    "typst": prof_typst,
    "astro": prof_astro,
}


def fmt(c: Counter[str]) -> str:
    return "".join(f"{k} {c[k]}\n" for k in sorted(c))


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("profiles", nargs="*", default=list(PROFILES))
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--update", action="store_true")
    args = ap.parse_args()

    failed = 0
    for name in args.profiles:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / name
            shutil.copytree(FIX / name, d)
            try:
                got = PROFILES[name](d)
            except SkipError as e:
                print(f"SKIP {name}: {e}")
                failed += args.strict
                continue
        exp_file = EXP / f"{name}.txt"
        if args.update:
            EXP.mkdir(exist_ok=True)
            exp_file.write_text(fmt(got))
            print(f"UPDATED {name}: {sum(got.values())} hits")
            continue
        rows = [r.split() for r in exp_file.read_text().splitlines() if r.strip()]
        want = Counter({k: int(v) for k, v in rows})
        if got == want:
            print(f"PASS {name}: {sum(got.values())} hits across {len(got)} rules")
        else:
            failed += 1
            print(f"FAIL {name}:")
            for k in sorted(set(got) | set(want)):
                if got[k] != want[k]:
                    print(f"   {k}: expected {want[k]}, got {got[k]}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
