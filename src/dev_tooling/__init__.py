"""Checks, hooks and dev-check for the dev-tooling kit."""

from __future__ import annotations

import io
import sys


def safe_stdout() -> None:
    """Print a character the console encoding can't show (cp1252 on Windows) as ?, not crash."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")
