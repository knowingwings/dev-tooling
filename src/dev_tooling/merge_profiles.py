"""Merge one profile's copy of a kit file into another's, for repos that combine profiles.

    python3 -m dev_tooling.merge_profiles <destination> <staged-file> <incoming-file>

adopt.sh calls this when two profiles (for example `astro,typst`) both provide the same file. The
staged file (the first profile's version, or an earlier merge) is rewritten in place with the
incoming profile's additions. The first profile wins wherever the two disagree.

    .pre-commit-config.yaml   repos and hook ids are combined; a hook both have keeps the first
                              profile's settings, but its `files` patterns are joined, and so are
                              the top-level `exclude` patterns
    patterns.toml             [[check.step]] tables with a new name and [[rule]] tables with a new
                              id are added; other tables are added only if the first lacks them
    .vscode/*.json            extensions, settings, tasks (by label) and launch configurations (by
                              name) are combined; only the first profile's build task stays default

Exit status 0 when the file was merged, 3 when this kind of file can't be merged (adopt.sh then
keeps the first profile's version and says so).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

UNSUPPORTED = 3
REPO_LINE = "  - repo:"
HOOK_LINE = re.compile(r"^      - id:\s*([^\s#]+)")
FILES_LINE = re.compile(r"^(\s+files:\s*)(\S.*?)\s*$")
EXCLUDE_LINE = re.compile(r"^exclude:\s*(\S.*?)\s*$")
TOML_HEADER = re.compile(r"^\[\[?([A-Za-z0-9_.-]+)\]\]?\s*(#.*)?$")
TOML_KEY = re.compile(r'^(name|id)\s*=\s*"([^"]*)"')


def join_patterns(first: str, second: str) -> str:
    """Two regexes as one that matches either; unchanged when they're the same."""
    return first if first == second else f"(?:{first})|(?:{second})"


def _trim(lines: list[str]) -> list[str]:
    while lines and not lines[-1].strip():
        lines = lines[:-1]
    return lines


def _split_precommit(text: str) -> tuple[list[str], list[list[str]]]:
    lines = text.splitlines(keepends=True)
    start = next(i for i, ln in enumerate(lines) if ln.rstrip() == "repos:")
    head, blocks = lines[: start + 1], []
    for ln in lines[start + 1 :]:
        if ln.startswith(REPO_LINE):
            blocks.append([ln])
        elif blocks:
            blocks[-1].append(ln)
        elif ln.strip():
            head.append(ln)
    return head, [_trim(b) for b in blocks]


def _hooks(block: list[str]) -> tuple[list[str], list[list[str]]]:
    first = next((i for i, ln in enumerate(block) if HOOK_LINE.match(ln)), len(block))
    entries: list[list[str]] = []
    for ln in block[first:]:
        if HOOK_LINE.match(ln):
            entries.append([ln])
        else:
            entries[-1].append(ln)
    return block[:first], entries


def _hook_id(entry: list[str]) -> str:
    m = HOOK_LINE.match(entry[0])
    return m.group(1) if m else ""


def _join_files(target: list[str], incoming: list[str]) -> list[str]:
    new = next((FILES_LINE.match(ln) for ln in incoming if FILES_LINE.match(ln)), None)
    if new is None:
        return target
    out = []
    for ln in target:
        m = FILES_LINE.match(ln)
        out.append(f"{m.group(1)}{join_patterns(m.group(2), new.group(2))}\n" if m else ln)
    return out


def _merge_hooks(target: list[str], incoming: list[str]) -> list[str]:
    head, entries = _hooks(target)
    ids = [_hook_id(e) for e in entries]
    for entry in _hooks(incoming)[1]:
        entry_id = _hook_id(entry)
        if entry_id in ids:
            i = ids.index(entry_id)
            entries[i] = _join_files(entries[i], entry)
        else:
            spaced = any(not e[-1].strip() for e in entries[:-1])
            if spaced and entries and entries[-1][-1].strip():
                entries[-1] = [*entries[-1], "\n"]
            entries.append(_trim(entry) if spaced else entry)
            ids.append(entry_id)
    return head + [ln for e in entries for ln in e]


def _merge_head(first: list[str], second: list[str]) -> list[str]:
    out = list(first)
    comments = [ln for ln in second if ln.startswith("#") and ln not in first]
    last_comment = max((i for i, ln in enumerate(out) if ln.startswith("#")), default=-1)
    out[last_comment + 1 : last_comment + 1] = comments
    theirs = next((EXCLUDE_LINE.match(ln) for ln in second if EXCLUDE_LINE.match(ln)), None)
    if theirs is None:
        return out
    for i, ln in enumerate(out):
        mine = EXCLUDE_LINE.match(ln)
        if mine:
            out[i] = f"exclude: {join_patterns(mine.group(1), theirs.group(1))}\n"
            return out
    repos = out.index(next(ln for ln in out if ln.rstrip() == "repos:"))
    out[repos:repos] = [f"exclude: {theirs.group(1)}\n", "\n"]
    return out


def merge_precommit(first: str, second: str) -> str:
    """Combine two pre-commit configs written in the kit's layout."""
    head_a, blocks_a = _split_precommit(first)
    head_b, blocks_b = _split_precommit(second)
    urls = [b[0] for b in blocks_a]
    for block in blocks_b:
        if block[0] in urls:
            i = urls.index(block[0])
            blocks_a[i] = _merge_hooks(blocks_a[i], block)
        else:
            blocks_a.append(block)
            urls.append(block[0])
    head = _merge_head(head_a, head_b)
    body = "\n".join("".join(b) for b in blocks_a)
    return "".join(head) + body


def _toml_chunks(text: str) -> list[list[str]]:
    chunks: list[list[str]] = [[]]
    in_string = ""
    for ln in text.splitlines(keepends=True):
        if not in_string and TOML_HEADER.match(ln):
            chunks.append([ln])
        else:
            chunks[-1].append(ln)
        for quote in ('"""', "'''"):
            if ln.count(quote) % 2 and in_string in ("", quote):
                in_string = "" if in_string else quote
    return chunks


def _chunk_key(chunk: list[str]) -> tuple[str, str]:
    m = TOML_HEADER.match(chunk[0]) if chunk else None
    if m is None:
        return ("", "")
    header = chunk[0].split("#")[0].strip()
    if header.startswith("[["):
        found = next((TOML_KEY.match(ln) for ln in chunk[1:] if TOML_KEY.match(ln)), None)
        return (header, found.group(2) if found else "")
    return (header, "")


def _own_lines(chunk: list[str]) -> list[str]:
    end = len(chunk)
    while end > 1 and (not chunk[end - 1].strip() or chunk[end - 1].lstrip().startswith("#")):
        end -= 1
    return chunk[:end]


def merge_patterns(first: str, second: str) -> str:
    """Add the second patterns.toml's new check steps, rules and missing tables to the first."""
    chunks = _toml_chunks(first)
    keys = [_chunk_key(c) for c in chunks]
    headers = {k[0] for k in keys}
    steps_at = max((i for i, k in enumerate(keys) if k[0] == "[[check.step]]"), default=-1)
    new_steps: list[list[str]] = []
    new_other: list[list[str]] = []
    for chunk in _toml_chunks(second)[1:]:
        key = _chunk_key(chunk)
        if key in keys or (not key[0].startswith("[[") and key[0] in headers):
            continue
        target = new_steps if key[0] == "[[check.step]]" else new_other
        target.append([*_own_lines(chunk), "\n"])
    if new_steps and steps_at >= 0:
        last = chunks[steps_at]
        own = _own_lines(last)
        chunks[steps_at : steps_at + 1] = [[*own, "\n"], *new_steps, last[len(own) :]]
    else:
        new_other = new_steps + new_other
    chunks += new_other
    out = "".join("".join(c) for c in chunks).rstrip("\n") + "\n"
    tomllib.loads(out)
    return out


def strip_jsonc(text: str) -> str:
    """JSON from JSONC: drop // and /* */ comments and trailing commas, leave strings alone."""
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i : j + 1])
            i = j + 1
        elif text.startswith("//", i):
            i = text.find("\n", i) if "\n" in text[i:] else n
        elif text.startswith("/*", i):
            i = text.index("*/", i) + 2
        else:
            out.append(c)
            i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def _leading_comments(text: str) -> list[str]:
    lines = []
    for ln in text.splitlines():
        if ln.lstrip().startswith("//"):
            lines.append(ln)
        elif ln.strip():
            break
    return lines


KeyPath = tuple[str | int, ...]
SCALAR = re.compile(r"-?\d[\d.eE+-]*|true|false|null")


def jsonc_comments(text: str) -> dict[KeyPath, list[str]]:
    """The comments inside a JSONC document, by the path of the key or element that follows them.

    A comment before an object's key or an array's element is stored under that item's path, for
    example ("clangd.arguments", 4). A comment just before a closing bracket goes with that
    container, and one after the document's last item with the empty path. Comments before the
    document's first bracket are its leading comments (see _leading_comments), so they're skipped.
    """
    found: dict[KeyPath, list[str]] = {}
    frames: list[list[str | int | None]] = []
    pending: list[str] = []
    expect_key = False

    def at() -> KeyPath:
        return tuple(f[1] for f in frames[:-1] if f[1] is not None)

    def flush(path: KeyPath) -> None:
        if pending:
            found.setdefault(path, []).extend(pending)
            pending.clear()

    def start_element() -> None:
        if frames and frames[-1][0] == "[":
            index = frames[-1][1]
            frames[-1][1] = index + 1 if isinstance(index, int) else 0
            flush((*at(), frames[-1][1]))

    i, n = 0, len(text)
    while i < n:
        c = text[i]
        scalar = SCALAR.match(text, i)
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            if expect_key:
                frames[-1][1] = json.loads(text[i : j + 1])
                flush((*at(), frames[-1][1]))
                expect_key = False
            else:
                start_element()
            i = j + 1
        elif text.startswith("//", i) or text.startswith("/*", i):
            j = text.find("\n", i) if text[i + 1] == "/" else text.index("*/", i) + 2
            j = n if j == -1 else j
            if frames:
                pending.append(text[i:j].strip())
            i = j
        elif c in "{[":
            start_element()
            frames.append([c, None])
            expect_key = c == "{"
            i += 1
        elif c in "}]":
            flush(at())
            frames.pop()
            i += 1
        elif c == ",":
            expect_key = bool(frames) and frames[-1][0] == "{"
            i += 1
        elif scalar:
            start_element()
            i = scalar.end()
        else:
            i += 1
    flush(())
    return found


def _place(path: KeyPath, source: object, merged: object) -> KeyPath | None:
    """The path in `merged` of the item at `path` in `source`, or None when merged dropped it.

    An array element is found by identity, so a comment stays with the element it describes, and
    is dropped with an array that the other profile's array replaced.
    """
    out: list[str | int] = []
    for step in path:
        if isinstance(step, str):
            if not (isinstance(source, dict) and isinstance(merged, dict)):
                return None
            if step not in source or step not in merged:
                return None
            source, merged = source[step], merged[step]
            out.append(step)
            continue
        if not (isinstance(source, list) and isinstance(merged, list) and step < len(source)):
            return None
        item = source[step]
        index = (
            step if merged is source else next((k for k, x in enumerate(merged) if x is item), None)
        )
        if index is None:
            return None
        source, merged = item, merged[index]
        out.append(index)
    return tuple(out)


def _dump(
    value: object, comments: dict[KeyPath, list[str]], path: KeyPath = (), level: int = 0
) -> str:
    """JSON as json.dumps(indent=2) writes it, with each comment before the item it is about."""
    pad, inner = "  " * level, "  " * (level + 1)
    if isinstance(value, dict) and value:
        items = [
            ((*path, k), json.dumps(k, ensure_ascii=False) + ": ", v) for k, v in value.items()
        ]
        brackets = "{}"
    elif isinstance(value, list) and value:
        items = [((*path, k), "", v) for k, v in enumerate(value)]
        brackets = "[]"
    else:
        return json.dumps(value, ensure_ascii=False)
    parts = []
    for where, label, item in items:
        notes = "".join(f"{inner}{c}\n" for c in comments.get(where, []))
        parts.append(f"{notes}{inner}{label}{_dump(item, comments, where, level + 1)}")
    return f"{brackets[0]}\n" + ",\n".join(parts) + f"\n{pad}{brackets[1]}"


def _merge_dict(first: dict[str, object], second: dict[str, object]) -> dict[str, object]:
    out = dict(first)
    for key, value in second.items():
        mine = out.get(key)
        if key not in out:
            out[key] = value
        elif isinstance(mine, dict) and isinstance(value, dict):
            out[key] = _merge_dict(mine, value)
    return out


def _union(first: list[object], second: list[object], key: str | None) -> list[object]:
    out = list(first)
    seen = [x.get(key) if key and isinstance(x, dict) else x for x in first]
    for item in second:
        ident = item.get(key) if key and isinstance(item, dict) else item
        if ident not in seen:
            out.append(item)
            seen.append(ident)
    return out


def _is_default_build(task: object) -> bool:
    group = task.get("group") if isinstance(task, dict) else None
    return isinstance(group, dict) and group.get("kind") == "build" and bool(group.get("isDefault"))


def merge_vscode(name: str, first: str, second: str) -> str:
    """Combine two VS Code JSONC files of the same kind (extensions, settings, tasks, launch)."""
    a = json.loads(strip_jsonc(first))
    b = json.loads(strip_jsonc(second))
    if name == "extensions.json":
        merged = {
            **a,
            "recommendations": _union(
                a.get("recommendations", []), b.get("recommendations", []), None
            ),
        }
    elif name == "tasks.json":
        incoming = b.get("tasks", [])
        if any(_is_default_build(t) for t in a.get("tasks", [])):
            incoming = [
                {**t, "group": {"kind": "build"}} if _is_default_build(t) else t for t in incoming
            ]
        merged = {**a, "tasks": _union(a.get("tasks", []), incoming, "label")}
    elif name == "launch.json":
        merged = {
            **a,
            "configurations": _union(
                a.get("configurations", []), b.get("configurations", []), "name"
            ),
        }
    else:
        merged = _merge_dict(a, b)
    placed: dict[KeyPath, list[str]] = {}
    for source, text in ((a, first), (b, second)):
        for path, lines in jsonc_comments(text).items():
            where = _place(path, source, merged)
            if where is not None:
                bucket = placed.setdefault(where, [])
                bucket += [ln for ln in lines if ln not in bucket]
    leading = _leading_comments(first)
    leading += [c for c in _leading_comments(second) + placed.pop((), []) if c not in leading]
    return "".join(f"{c}\n" for c in leading) + _dump(merged, placed) + "\n"


def merge(destination: str, first: str, second: str) -> str | None:
    """The merged text, or None when files like `destination` can't be merged."""
    name = Path(destination).name
    if name == ".pre-commit-config.yaml":
        return merge_precommit(first, second)
    if name == "patterns.toml":
        return merge_patterns(first, second)
    if Path(destination).parent.name == ".vscode" and name.endswith(".json"):
        return merge_vscode(name, first, second)
    return None


def main() -> int:
    if len(sys.argv) != 4:
        sys.stderr.write(__doc__ or "")
        return 2
    destination, staged, incoming = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    merged = merge(destination, staged.read_text(), incoming.read_text())
    if merged is None:
        return UNSUPPORTED
    staged.write_text(merged)
    return 0


if __name__ == "__main__":
    sys.exit(main())
