"""Edge cases for the comment tokenizer and policy: python3 -m unittest tests/test_check_comments.py"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from robot_dev_kit.check_comments import (  # noqa: E402
    DEFAULTS,
    Config,
    c_like_comments,
    python_comments,
    verdict,
)

CFG = Config(**DEFAULTS)  # type: ignore[arg-type]


def texts(src: str, *, rust: bool = False) -> list[str]:
    return [c.text for c in c_like_comments(src, rust=rust)]


def flagged(src: str, *, rust: bool = False, py: bool = False) -> list[str]:
    found = python_comments(src) if py else c_like_comments(src, rust=rust)
    return [r for c in found if (r := verdict(c, CFG))]


class Tokenizer(unittest.TestCase):
    def test_url_in_string_is_not_a_comment(self) -> None:
        self.assertEqual(texts('const char *u = "http://x.io/a"; int x;'), [])

    def test_escaped_quote_in_string(self) -> None:
        self.assertEqual(texts(r'const char *s = "a\"//b"; // real'), ["// real"])

    def test_char_literals(self) -> None:
        self.assertEqual(texts("char a = '/'; char b = '\\''; char c = '\"'; // real"), ["// real"])

    def test_cpp_digit_separator(self) -> None:
        self.assertEqual(texts("int n = 1'000'000; // real"), ["// real"])

    def test_cpp_raw_string(self) -> None:
        self.assertEqual(texts('auto s = R"x(// not a comment)x"; /* real */'), ["/* real */"])

    def test_block_comment_spans_lines(self) -> None:
        (c,) = c_like_comments("int a;\n/* one\n two */\nint b;", rust=False)
        self.assertEqual((c.line, c.end_line), (2, 3))

    def test_rust_lifetimes_and_labels(self) -> None:
        src = "fn f<'a>(x: &'a str) -> &'static str { 'outer: loop { break 'outer; } x } // real"
        self.assertEqual(texts(src, rust=True), ["// real"])

    def test_rust_char_and_byte(self) -> None:
        self.assertEqual(texts("let c = '\\u{1F600}'; let q = b'\"'; // real", rust=True), ["// real"])

    def test_rust_raw_string(self) -> None:
        self.assertEqual(texts('let s = r#"// "not" a comment"#; // real', rust=True), ["// real"])

    def test_rust_nested_block_comment(self) -> None:
        self.assertEqual(texts("/* a /* b */ c */ let x = 1;", rust=True), ["/* a /* b */ c */"])

    def test_python_hash_in_string_and_docstring(self) -> None:
        src = 'def f():\n    """Doc # not a comment."""\n    return "#x"  # real\n'
        self.assertEqual([c.text for c in python_comments(src)], ["# real"])

    def test_python_shebang_and_coding_ignored(self) -> None:
        src = "#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nx = 1\n"
        self.assertEqual(python_comments(src), [])


class Policy(unittest.TestCase):
    def test_plain_comment_flagged(self) -> None:
        self.assertEqual(flagged("// increase gain for the new motor\nint g;"), ["no-comments"])

    def test_doc_comments_allowed(self) -> None:
        src = "/// Duty cycle in [0, 1].\n//! Motor driver.\n/** Doxygen. */\nint d;"
        self.assertEqual(flagged(src, rust=True), [])

    def test_four_slashes_is_not_doc(self) -> None:
        self.assertEqual(flagged("//// banner\nint x;"), ["no-comments"])

    def test_safety_allowed(self) -> None:
        self.assertEqual(flagged("// SAFETY: ptr is valid for len bytes\nunsafe {}", rust=True), [])

    def test_ref_with_source_allowed(self) -> None:
        self.assertEqual(flagged("// REF(RM0090 10.3.2): DMA2 only does mem-to-mem\n"), [])

    def test_ref_without_source_flagged(self) -> None:
        self.assertEqual(flagged("// REF(): trust me\n"), ["no-comments-ref-needs-source"])
        self.assertEqual(flagged("// REF(RM0090)\n"), ["no-comments-ref-needs-source"])

    def test_suppressions_allowed(self) -> None:
        src = "int a; // NOLINT(bugprone-x) vendor macro\n// lint-allow(fw-no-double): host-only tool\n"
        self.assertEqual(flagged(src), [])
        self.assertEqual(flagged("import os  # noqa: S605 fixed command\n", py=True), [])

    def test_licence_header_allowed(self) -> None:
        self.assertEqual(flagged("// SPDX-License-Identifier: MIT\n/* Copyright 2026 Acme */\n"), [])


class NewLinesOnly(unittest.TestCase):
    def test_only_added_comments_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
            subprocess.run([*git, "init", "-q"], cwd=root, check=True)
            f = root / "m.c"
            f.write_text("// old comment\nint a;\n")
            subprocess.run([*git, "add", "-A"], cwd=root, check=True)
            subprocess.run([*git, "commit", "-qm", "base"], cwd=root, check=True)
            f.write_text("// old comment\nint a;\n// new comment\nint b;\n")
            subprocess.run([*git, "add", "-A"], cwd=root, check=True)
            src = Path(__file__).resolve().parent.parent / "src"
            p = subprocess.run(
                [sys.executable, "-m", "robot_dev_kit.check_comments", "m.c"],
                cwd=root, capture_output=True, text=True, check=False,
                env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin:/usr/local/bin"},
            )
            self.assertEqual(p.returncode, 1)
            self.assertIn("m.c:3:1: [no-comments]", p.stdout)
            self.assertNotIn("m.c:1:", p.stdout)


if __name__ == "__main__":
    unittest.main()
