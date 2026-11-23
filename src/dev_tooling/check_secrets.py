#!/usr/bin/env python3
"""Keep secrets out of git: block private keys, known token formats and plain values in env files.

    private-key        a PEM private key block
    token              a token with a well-known prefix
                       (GitHub, Anthropic, OpenAI, AWS, Slack, 1Password)
    env-plain-secret   an env file sets a KEY/TOKEN/SECRET/PASSWORD variable to a literal value

Secrets live in 1Password. An env file holds `op://<vault>/<item>/<field>` references and runs with
`op run --env-file=<file> -- <command>`. For a fake value in a test, put
`lint-allow(secret): <reason>` on the same line.

    check-secrets [files...]     # pre-commit: staged files
    check-secrets                # every tracked file
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dev_tooling import safe_stdout
from dev_tooling.check_comments import tracked_files

TOKENS = [
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b")),
    ("GitHub fine-grained token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{50,}\b")),
    ("Anthropic API key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("OpenAI API key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{40,}")),
    ("AWS access key id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("Slack token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("1Password service account token", re.compile(r"\bops_[A-Za-z0-9_-]{40,}")),
]
PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY(?: BLOCK)?-----")
ENV_NAME = re.compile(r"(?:^|/)(?:\.env(?:\.[\w.-]+)?|[\w.-]+\.env)$")
ENV_EXAMPLE = re.compile(r"(?:example|sample|template|dist)", re.I)
ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$")
SECRET_VAR = re.compile(r"(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD|PWD|PASS|CREDENTIALS?|AUTH)$", re.I)
SAFE_VALUE = re.compile(r"""^(?:["']?(?:op://\S+|\$\{?\w+\}?|<[^>]*>|)["']?)$""")
ALLOW = re.compile(r"lint-allow\(secret\)\s*:\s*\S.{8,}")

FIX = (
    "Remove it, and rotate it if it was ever pushed. "
    "Store it in 1Password and read it at run time: "
    "`op read op://<vault>/<item>/<field>`, or put the op:// reference in an env file and run "
    "`op run --env-file=<file> -- <command>`."
)


def problems(rel: str, text: str) -> list[tuple[int, str, str]]:
    found: list[tuple[int, str, str]] = []
    is_env = bool(ENV_NAME.search(rel)) and not ENV_EXAMPLE.search(rel)
    for n, line in enumerate(text.splitlines(), start=1):
        if ALLOW.search(line):
            continue
        if PRIVATE_KEY.search(line):
            found.append((n, "private-key", f"A private key. {FIX}"))
            continue
        for name, rx in TOKENS:
            if rx.search(line):
                found.append((n, "token", f"Looks like a {name}. {FIX}"))
                break
        else:
            m = ENV_LINE.match(line) if is_env and not line.lstrip().startswith("#") else None
            if m and SECRET_VAR.search(m.group(1)) and not SAFE_VALUE.match(m.group(2)):
                msg = f"{m.group(1)} has a literal value. Use an op:// reference instead. {FIX}"
                found.append((n, "env-plain-secret", msg))
    return found


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files", nargs="*")
    ap.add_argument("--root", type=Path, default=Path.cwd())
    args = ap.parse_args()
    safe_stdout()
    root = args.root.resolve()

    failures = 0
    for f in args.files or tracked_files(root):
        path = (root / f) if not Path(f).is_absolute() else Path(f)
        try:
            rel = path.resolve().relative_to(root).as_posix()
        except ValueError:
            rel = Path(f).as_posix()
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:
            continue
        for n, rule, msg in problems(rel, data.decode(errors="replace")):
            sys.stdout.write(f"{rel}:{n}: [{rule}] {msg}\n")
            failures += 1
    if failures:
        sys.stderr.write(f"\n{failures} possible secret(s). Nothing secret belongs in git.\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
