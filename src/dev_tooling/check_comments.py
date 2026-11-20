#!/usr/bin/env python3
"""No new comments: block comments on added lines unless they're one of the allowed forms.

Comments go stale, and agents use them to justify workarounds ("temporary hack because..."). The why
belongs where a tool checks it: a clearer name, a type or assert, a lint rule, a test, or the commit
message. Allowed forms:

    /// doc comment, //! module doc, /** doxygen */    (allow_doc_comments, default on)
    // SAFETY: why this unsafe block is sound        (clippy's undocumented_unsafe_blocks needs it)
    // REF(RM0090 10.3.2): DMA2 only for mem-to-mem  (a hardware fact, with its source)
    // lint-allow(rule): reason, NOLINT, noqa, pyright: ignore, type: ignore, clang-format off/on
    licence headers (Copyright / SPDX-License-Identifier)

Configured by an optional [comments] table in patterns.toml (see the profiles in lint/). By default
only comments on lines added in the staged change are checked, so existing code doesn't fail when
touched.

    check-comments [files...]            # pre-commit: staged files, staged additions only
    check-comments --base origin/main    # CI: lines added since a base ref
    check-comments --all-lines [files]   # audit every comment
"""

from __future__ import annotations

import argparse
import fnmatch
import io
import re
import shutil
import subprocess
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

C_FAMILY = {".c", ".h", ".cc", ".cpp", ".cxx", ".hh", ".hpp", ".hxx", ".ino"}
RUST = {".rs"}
PYTHON = {".py"}

DEFAULTS: dict[str, object] = {
    "enabled": True,
    "include": ["**/*.c", "**/*.h", "**/*.cpp", "**/*.hpp", "**/*.cc", "**/*.rs", "**/*.py"],
    "exclude": [
        "**/test/**",
        "**/tests/**",
        "test/**",
        "tests/**",
        "**/third_party/**",
        "**/vendor/**",
        "Drivers/**",
        "**/Drivers/**",
        "target/**",
        "build/**",
        "install/**",
        "**/launch/**",
    ],
    "allow_doc_comments": True,
    "new_lines_only": True,
    "allow": [
        "SAFETY:",
        "lint-allow(",
        "NOLINT",
        "noqa",
        "type: ignore",
        "pyright:",
        "clang-format",
        "fmt: off",
        "fmt: on",
        "fmt: skip",
        "SPDX-License-Identifier",
        "Copyright",
    ],
}

REF_OK = re.compile(r"\bREF\(\s*[^)\s][^)]*\)\s*:\s*\S")
REF_ANY = re.compile(r"\bREF\(")

MSG = (
    "No new comments: they go stale, and agents use them to justify workarounds. Put the why "
    "where a tool checks it: a clearer name, a type or assert, a lint rule, a test, or the commit "
    "message. Allowed: doc comments on public API, `SAFETY:` on unsafe, "
    "`REF(<datasheet/erratum/issue>): <fact>` "
    "for hardware facts code can't express, lint suppressions with a reason, licence headers."
)
MSG_REF = (
    "REF comments need a source: REF(<datasheet section, erratum id or issue URL>): <the fact>."
)


@dataclass
class Comment:
    line: int
    end_line: int
    col: int
    text: str
    doc: bool = False


@dataclass
class Config:
    enabled: bool = True
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    allow_doc_comments: bool = True
    new_lines_only: bool = True
    allow: list[str] = field(default_factory=list)


def _line_col(src: str, i: int, line_starts: list[int]) -> tuple[int, int]:
    lo, hi = 0, len(line_starts) - 1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if line_starts[mid] <= i:
            lo = mid
        else:
            hi = mid - 1
    return lo + 1, i - line_starts[lo] + 1


def c_like_comments(src: str, rust: bool) -> list[Comment]:
    """Comments in C, C++ or Rust source, skipping strings, chars, raw strings and lifetimes."""
    starts = [0] + [m.end() for m in re.finditer(r"\n", src)]
    out: list[Comment] = []
    i, n = 0, len(src)
    while i < n:
        ch = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = src.find("\n", i)
            j = n if j == -1 else j
            text = src[i:j]
            doc = (text.startswith("///") and not text.startswith("////")) or text.startswith("//!")
            line, col = _line_col(src, i, starts)
            out.append(Comment(line, line, col, text, doc))
            i = j
        elif ch == "/" and nxt == "*":
            depth, j = 1, i + 2
            while j < n and depth:
                if src.startswith("*/", j):
                    depth -= 1
                    j += 2
                elif rust and src.startswith("/*", j):
                    depth += 1
                    j += 2
                else:
                    j += 1
            text = src[i:j]
            doc = (text.startswith("/**") and not text.startswith("/**/")) or text.startswith("/*!")
            line, col = _line_col(src, i, starts)
            end, _ = _line_col(src, max(j - 1, i), starts)
            out.append(Comment(line, end, col, text, doc))
            i = j
        elif (
            rust
            and ch == "r"
            and (nxt == '"' or nxt == "#")
            and not (i and (src[i - 1].isalnum() or src[i - 1] == "_"))
        ):
            m = re.match(r'r(#*)"', src[i:])
            if m:
                close = '"' + m.group(1)
                j = src.find(close, i + m.end())
                i = n if j == -1 else j + len(close)
            else:
                i += 1
        elif not rust and ch == "R" and nxt == '"':
            m = re.match(r'R"([^(\s]{0,16})\(', src[i:])
            if m:
                close = ")" + m.group(1) + '"'
                j = src.find(close, i + m.end())
                i = n if j == -1 else j + len(close)
            else:
                i += 1
        elif ch == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" else 1
            i = j + 1
        elif ch == "'":
            prev = src[i - 1] if i else ""
            cpp_digit_separator_or_prefix = not rust and (prev.isalnum() or prev == "_")
            if cpp_digit_separator_or_prefix:
                i += 1
                continue
            char_literal = re.match(
                r"'(\\(x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]+\}|.)|[^\\'\n])'", src[i:]
            )
            rust_lifetime_or_label = rust and not char_literal
            if char_literal:
                i += char_literal.end()
            elif rust_lifetime_or_label:
                i += 1
            else:
                j = src.find("'", i + 1)
                i = n if j == -1 else j + 1
        else:
            i += 1
    return out


def python_comments(src: str) -> list[Comment]:
    """Comments in Python source.

    On a syntax error, returns those found before it: ruff reports the error itself.
    """
    out: list[Comment] = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type == tokenize.COMMENT:
                line, col = tok.start
                if line == 1 and tok.string.startswith("#!"):
                    continue
                if line <= 2 and re.match(r"#.*coding[:=]", tok.string):
                    continue
                out.append(Comment(line, line, col + 1, tok.string))
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return out
    return out


def comments_in(path: Path, src: str) -> list[Comment]:
    ext = path.suffix.lower()
    if ext in PYTHON:
        return python_comments(src)
    if ext in RUST:
        return c_like_comments(src, rust=True)
    if ext in C_FAMILY:
        return c_like_comments(src, rust=False)
    return []


def verdict(c: Comment, cfg: Config) -> str | None:
    """None if the comment is allowed, else the rule id."""
    if REF_ANY.search(c.text):
        return None if REF_OK.search(c.text) else "no-comments-ref-needs-source"
    if c.doc and cfg.allow_doc_comments:
        return None
    if any(tag in c.text for tag in cfg.allow):
        return None
    return "no-comments"


def _match_any(rel: str, globs: list[str]) -> bool:
    for g in globs:
        variants = {g}
        while True:
            new = {
                v[:i] + v[i + 3 :]
                for v in variants
                for i in range(len(v))
                if v.startswith("**/", i)
            }
            if new <= variants:
                break
            variants |= new
        if any(fnmatch.fnmatch(rel, v) for v in variants):
            return True
    return False


def load_config(root: Path, path: Path | None) -> Config:
    data: dict[str, object] = dict(DEFAULTS)
    cfg_file = path or root / "patterns.toml"
    if cfg_file.exists():
        data.update(tomllib.loads(cfg_file.read_text()).get("comments", {}))
    return Config(**{k: data[k] for k in Config.__dataclass_fields__ if k in data})


def _git() -> str:
    git = shutil.which("git")
    if git is None:
        sys.exit("check_comments: git not found on PATH")
    return git


def added_lines(root: Path, rel: str, base: str | None) -> set[int] | None:
    """Lines added in the staged change (or since `base`). None = not in git: treat all as new."""
    args = [_git(), "diff", "--no-color", "--unified=0"]
    args += [f"{base}...HEAD", "--"] if base else ["--cached", "--"]
    p = subprocess.run([*args, rel], cwd=root, capture_output=True, text=True, check=False)
    if p.returncode != 0:
        return None
    lines: set[int] = set()
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", p.stdout, re.M):
        start, count = int(m.group(1)), int(m.group(2) or "1")
        lines.update(range(start, start + count))
    return lines


def tracked_files(root: Path) -> list[str]:
    p = subprocess.run([_git(), "ls-files"], cwd=root, capture_output=True, text=True, check=True)
    return p.stdout.splitlines()


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files", nargs="*")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--base", default=None, help="check lines added since this git ref (CI)")
    ap.add_argument(
        "--all-lines", action="store_true", help="check every comment, not just new ones"
    )
    args = ap.parse_args()

    root = args.root.resolve()
    cfg = load_config(root, args.config)
    if not cfg.enabled:
        return 0
    only_new = cfg.new_lines_only and not args.all_lines

    failures = 0
    for f in args.files or tracked_files(root):
        path = (root / f) if not Path(f).is_absolute() else Path(f)
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = Path(f).as_posix()
        if not path.is_file() or not _match_any(rel, cfg.include) or _match_any(rel, cfg.exclude):
            continue
        found = comments_in(path, path.read_text(errors="replace"))
        if not found:
            continue
        new = added_lines(root, rel, args.base) if only_new else None
        for c in found:
            if new is not None and not any(ln in new for ln in range(c.line, c.end_line + 1)):
                continue
            rule = verdict(c, cfg)
            if rule:
                msg = MSG_REF if rule.endswith("ref-needs-source") else MSG
                sys.stdout.write(f"{rel}:{c.line}:{c.col}: [{rule}] {msg}\n")
                failures += 1
    if failures:
        sys.stderr.write(
            f"\n{failures} new comment(s). Say it in code, a check, or the commit message.\n"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
