#!/usr/bin/env python3
"""Prose length rules from ASD-STE100 (Simplified Technical English) for Markdown and Typst docs.

    sentence-too-long     more than 25 words in a descriptive sentence
    step-too-long         more than 20 words in a sentence of a numbered step (a procedure)
    paragraph-too-long    more than 6 sentences in a paragraph

Code blocks, inline code, headings, tables, HTML and Typst code lines are ignored. To keep one block
as it is, put `lint-allow(prose): <reason>` in a comment on the line above it
(`<!-- ... -->` in Markdown, `// ...` in Typst).

Configured by an optional [prose] table in patterns.toml. By default only blocks that contain a line
added in the staged change are checked, so existing docs don't fail when touched. A problem that the
old version of the file already had, with the same number of words and mostly the same words (a
spelling fix, for example), isn't reported either: the change didn't make it.

    check-prose [files...]            # pre-commit: staged files, changed blocks only
    check-prose --base origin/main    # CI: blocks changed since a base ref
    check-prose --all-lines [files]   # audit every block
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from dev_tooling import safe_stdout
from dev_tooling.check_comments import _match_any, added_lines, old_text, tracked_files

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

DEFAULTS: dict[str, object] = {
    "enabled": True,
    "include": ["README.md", "**/README.md", "docs/**/*.md", "**/*.typ"],
    "exclude": [
        "docs/agents/**",
        "CHANGELOG.md",
        "**/third_party/**",
        "**/vendor/**",
        "build/**",
        "target/**",
        "node_modules/**",
    ],
    "max_words": 25,
    "max_words_step": 20,
    "max_sentences": 6,
    "new_lines_only": True,
}

ALLOW = re.compile(r"lint-allow\(prose[\w-]*\)\s*:\s*(.*?)\s*(?:-->)?\s*$")
MIN_REASON = 10

MSG = {
    "sentence-too-long": "{n} words in a sentence; STE allows {limit} for descriptive text. "
    "Split it: one idea per sentence.",
    "step-too-long": "{n} words in a step; STE allows {limit} in a procedure. "
    "Give one instruction per sentence and start it with the verb.",
    "paragraph-too-long": "{n} sentences in a paragraph; STE allows {limit}. "
    "Split it so each paragraph has one topic.",
}

ABBREV = re.compile(r"\b(?:e\.g|i\.e|etc|vs|cf|approx|Fig|fig|No|no|Ref|Sec|Eq|Rev|max|min)\.")
SENTENCE_END = re.compile(r"[.!?][)\]\"'\u2019\u201d*_]*(?=\s+\S|\s*$)")
WORD = re.compile(r"[A-Za-z0-9][\w'\u2019.%/+-]*")


@dataclass
class Config:
    enabled: bool = True
    include: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)
    max_words: int = 25
    max_words_step: int = 20
    max_sentences: int = 6
    new_lines_only: bool = True


@dataclass
class Block:
    line: int
    lines: list[str]
    kind: str
    allowed: bool = False

    @property
    def end_line(self) -> int:
        return self.line + len(self.lines) - 1


def load_config(root: Path, path: Path | None) -> Config:
    data: dict[str, object] = dict(DEFAULTS)
    cfg_file = path or root / "patterns.toml"
    if cfg_file.exists():
        data.update(tomllib.loads(cfg_file.read_text(encoding="utf-8")).get("prose", {}))
    return Config(**{k: data[k] for k in Config.__dataclass_fields__ if k in data})


MD_ITEM = re.compile(r"^\s*(?:[-*+]|(\d+)[.)])\s+")
TYP_ITEM = re.compile(r"^\s*(?:(-)|(\+)|/\s[^:]*:)\s+")
MD_SKIP = re.compile(r"^\s*(?:#|\||<|\[[^\]]+\]:|---\s*$|===+\s*$|!\[)")
TYP_SKIP = re.compile(r"^\s*(?:=|#|//|\$|<\w[\w-]*>\s*$)")


def blocks(src: str, typst: bool) -> list[Block]:
    """Split a document into prose blocks: paragraphs and list items, with their kind."""
    out: list[Block] = []
    cur: Block | None = None
    fence: str | None = None
    allow_next = False
    skip = TYP_SKIP if typst else MD_SKIP
    item = TYP_ITEM if typst else MD_ITEM
    front_matter = not typst and src.startswith("---\n")

    def close() -> None:
        nonlocal cur
        if cur is not None:
            out.append(cur)
        cur = None

    for n, raw in enumerate(src.splitlines(), start=1):
        line = raw.rstrip()
        if front_matter:
            if n > 1 and line.strip() == "---":
                front_matter = False
            continue
        fence_m = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence:
            if fence_m and fence_m.group(1)[0] == fence[0] and len(fence_m.group(1)) >= len(fence):
                fence = None
            continue
        if fence_m:
            close()
            fence = fence_m.group(1)
            continue
        allow_m = ALLOW.search(line)
        if allow_m and not line.lstrip().startswith(("-", "*", "+")) and _is_comment(line, typst):
            close()
            allow_next = len(allow_m.group(1)) >= MIN_REASON
            continue
        if not line.strip():
            close()
            continue
        if skip.match(line) or (not typst and cur is None and line.startswith("    ")):
            close()
            allow_next = False
            continue
        text = line
        if not typst:
            text = re.sub(r"^\s*>\s?", "", text)
        m = item.match(text)
        if m:
            close()
            numbered = bool(m.group(2)) if typst else bool(m.group(1))
            cur = Block(n, [text[m.end() :]], "step" if numbered else "item", allow_next)
            allow_next = False
            continue
        if cur is None:
            cur = Block(n, [text.strip()], "para", allow_next)
            allow_next = False
        else:
            cur.lines.append(text.strip())
    close()
    return out


def _is_comment(line: str, typst: bool) -> bool:
    s = line.strip()
    return s.startswith("//") if typst else s.startswith("<!--")


def _plain(text: str, typst: bool) -> str:
    text = re.sub(r"`[^`]*`", "CODE", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    if typst:
        text = re.sub(r"\$[^$]*\$", "MATH", text)
        text = re.sub(r"#[A-Za-z][\w.-]*(?:\([^()]*\))?", " ", text)
        text = re.sub(r"@[\w:.-]+", "REF", text)
        text = text.replace("[", " ").replace("]", " ")
    return re.sub(r"[*_~]+", "", text)


def sentences(block: Block, typst: bool) -> list[tuple[int, str]]:
    """(line, sentence) for each sentence in a block."""
    joined = "\n".join(block.lines)
    masked = ABBREV.sub(lambda m: m.group(0)[:-1] + "\x00", joined)
    found: list[tuple[int, str]] = []
    start = 0
    for m in SENTENCE_END.finditer(masked):
        found.append((start, joined[start : m.end()]))
        start = m.end()
    if joined[start:].strip():
        found.append((start, joined[start:]))
    result = []
    for offset, s in found:
        lead = len(s) - len(s.lstrip())
        line = block.line + joined[: offset + lead].count("\n")
        plain = _plain(s, typst).strip()
        if WORD.search(plain):
            result.append((line, plain))
    return result


def problems(src: str, typst: bool, cfg: Config) -> list[tuple[int, Block, str, str]]:
    """(line, block, rule, message) for every sentence or paragraph that breaks a rule."""
    found = []
    for b in blocks(src, typst):
        if b.allowed:
            continue
        sents = sentences(b, typst)
        limit = cfg.max_words_step if b.kind == "step" else cfg.max_words
        rule = "step-too-long" if b.kind == "step" else "sentence-too-long"
        for line, s in sents:
            n = len(WORD.findall(s))
            if n > limit:
                found.append((line, b, rule, MSG[rule].format(n=n, limit=limit)))
        if b.kind == "para" and len(sents) > cfg.max_sentences:
            msg = MSG["paragraph-too-long"].format(n=len(sents), limit=cfg.max_sentences)
            found.append((b.line, b, "paragraph-too-long", msg))
    return found


def unit_words(block: Block, line: int, rule: str, typst: bool, cfg: Config) -> list[str]:
    """The words of the sentence (for paragraph-too-long, the paragraph) that a problem is about."""
    sents = sentences(block, typst)
    if rule == "paragraph-too-long":
        return [w for _, s in sents for w in WORD.findall(s)]
    limit = cfg.max_words_step if block.kind == "step" else cfg.max_words
    for ln, s in sents:
        words = WORD.findall(s)
        if ln == line and len(words) > limit:
            return words
    return []


def carried_over(words: list[str], rule: str, old: list[tuple[str, list[str]]]) -> bool:
    """True when the old file had this problem in a unit of the same length with 80% the same words.

    The matching old problem is removed from `old`, so each old problem excuses one new one only.
    """
    for i, (old_rule, old_words) in enumerate(old):
        if old_rule != rule or len(old_words) != len(words) or not words:
            continue
        same = sum(a == b for a, b in zip(words, old_words, strict=True))
        if same * 5 >= len(words) * 4:
            del old[i]
            return True
    return False


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files", nargs="*")
    ap.add_argument("--config", type=Path, default=None)
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--base", default=None, help="check blocks changed since this git ref (CI)")
    ap.add_argument("--all-lines", action="store_true", help="check every block, not just changed")
    args = ap.parse_args()
    safe_stdout()

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
        typst = path.suffix == ".typ"
        found = problems(path.read_text(encoding="utf-8", errors="replace"), typst, cfg)
        new = added_lines(root, rel, args.base) if only_new and found else None
        before = old_text(root, rel, args.base) if new is not None else None
        old = (
            [(r, unit_words(b, ln, r, typst, cfg)) for ln, b, r, _ in problems(before, typst, cfg)]
            if before is not None
            else []
        )
        for line, b, rule, msg in found:
            carried = bool(old) and carried_over(unit_words(b, line, rule, typst, cfg), rule, old)
            if new is not None and not any(ln in new for ln in range(b.line, b.end_line + 1)):
                continue
            if carried:
                continue
            sys.stdout.write(f"{rel}:{line}: [{rule}] {msg}\n")
            failures += 1
    if failures:
        sys.stderr.write(
            f"\n{failures} STE length problem(s). "
            "Short sentences are easier to read and translate.\n"
        )
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
