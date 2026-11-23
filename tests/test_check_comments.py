"""Comment tokenizer and policy edge cases.

Run: python3 -m unittest tests/test_check_comments.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dev_tooling.check_comments import (
    DEFAULTS,
    Config,
    RemovedComments,
    c_like_comments,
    comment_words,
    python_comments,
    verdict,
)

CFG = Config(**DEFAULTS)  # type: ignore[arg-type]
SRC = Path(__file__).resolve().parent.parent / "src"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
FAIL_ON_LOCALE_ENCODING = ["-X", "warn_default_encoding", "-W", "error::EncodingWarning"]


def git(root: Path, *args: str) -> None:
    subprocess.run([*GIT, *args], cwd=root, check=True, capture_output=True)


def check(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "dev_tooling.check_comments", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(SRC), "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )


def staged(old: str, new: str, name: str = "m.py") -> subprocess.CompletedProcess[str]:
    """check-comments on a staged change from `old` to `new`, as the pre-commit hook runs it."""
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        git(root, "init", "-q")
        (root / name).write_text(old)
        git(root, "add", "-A")
        git(root, "commit", "-qm", "base")
        (root / name).write_text(new)
        git(root, "add", "-A")
        return check(root, name)


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
        self.assertEqual(
            texts("let c = '\\u{1F600}'; let q = b'\"'; // real", rust=True), ["// real"]
        )

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
        src = (
            "int a; // NOLINT(bugprone-x) vendor macro\n"
            "// lint-allow(fw-no-double): host-only tool\n"
        )
        self.assertEqual(flagged(src), [])
        self.assertEqual(flagged("import os  # noqa: S605 fixed command\n", py=True), [])

    def test_licence_header_allowed(self) -> None:
        self.assertEqual(
            flagged("// SPDX-License-Identifier: MIT\n/* Copyright 2026 Acme */\n"), []
        )


class NewLinesOnly(unittest.TestCase):
    def test_only_added_comments_flagged(self) -> None:
        old = "// old comment\nint a;\n"
        p = staged(old, old + "// new comment\nint b;\n", "m.c")
        self.assertEqual(p.returncode, 1)
        self.assertIn("m.c:3:1: [no-comments]", p.stdout)
        self.assertNotIn("m.c:1:", p.stdout)


LONG = (
    "def f():\n"
    "    # Check the answer before taking the write lock; slow checks must not block other"
    " writers.\n"
    "    return 1\n"
)


class MovedComments(unittest.TestCase):
    def test_rewrapped_comment_is_not_new(self) -> None:
        wrapped = (
            "def f():\n"
            "    # Check the answer before taking the write lock; slow checks\n"
            "    # must not block other writers.\n"
            "    return 1\n"
        )
        p = staged(LONG, wrapped)
        self.assertEqual((p.returncode, p.stdout), (0, ""))

    def test_reindented_block_is_not_new(self) -> None:
        old = "# Two lines\n# of reasons.\nx = 1\n"
        new = "if True:\n    # Two lines\n    # of reasons.\n    x = 1\n"
        self.assertEqual(staged(old, new).returncode, 0)

    def test_trailing_comment_on_changed_code_is_not_new(self) -> None:
        old = "x = compute(1)  # the sensor reports in tenths\n"
        new = "x = compute(2)  # the sensor reports in tenths\n"
        self.assertEqual(staged(old, new).returncode, 0)

    def test_block_comment_rewritten_as_line_comments(self) -> None:
        old = "/* Reset the watchdog\n * before the flash erase. */\nint a;\n"
        new = "// Reset the watchdog before the flash erase.\nint a;\n"
        self.assertEqual(staged(old, new, "m.c").returncode, 0)

    def test_added_word_is_new(self) -> None:
        old = "x = 1  # keep in sync with the firmware\n"
        new = "x = 2  # keep in sync with the firmware, temporary hack\n"
        p = staged(old, new)
        self.assertEqual(p.returncode, 1)
        self.assertIn("m.py:1:", p.stdout)

    def test_copied_comment_is_new(self) -> None:
        old = "# the sensor reports in tenths\nx = 1\n"
        new = "# the sensor reports in tenths\nx = 1\n# the sensor reports in tenths\ny = 2\n"
        p = staged(old, new)
        self.assertEqual(p.returncode, 1)
        self.assertIn("m.py:3:", p.stdout)

    def test_each_removed_comment_excuses_one_copy(self) -> None:
        old = "x = 1  # tenths of a degree\n"
        new = "x = 2  # tenths of a degree\ny = 3  # tenths of a degree\n"
        p = staged(old, new)
        self.assertEqual(p.returncode, 1)
        self.assertNotIn("m.py:1:", p.stdout)
        self.assertIn("m.py:2:", p.stdout)

    def test_ci_base_mode(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            git(root, "init", "-q", "-b", "main")
            (root / "m.py").write_text(LONG)
            git(root, "add", "-A")
            git(root, "commit", "-qm", "base")
            git(root, "switch", "-qc", "feat/x")
            wrapped = LONG.replace("slow checks must", "slow checks\n    # must")
            (root / "m.py").write_text(wrapped + "# a new reason\n")
            git(root, "commit", "-qam", "wrap")
            p = check(root, "--base", "main", "m.py")
            self.assertEqual(p.returncode, 1)
            self.assertEqual(p.stdout.count("[no-comments]"), 1)
            self.assertIn("m.py:5:", p.stdout)

    def test_non_ascii_diff_with_a_non_utf8_locale(self) -> None:
        bar = "━━ ● ○ ■"
        for base in (None, "main"):
            with self.subTest(base=base), tempfile.TemporaryDirectory() as d:
                root = Path(d)
                git(root, "init", "-q", "-b", "main")
                (root / "m.py").write_text(f'BAR = "{bar}"\n', encoding="utf-8")
                git(root, "add", "-A")
                git(root, "commit", "-qm", "base")
                git(root, "switch", "-qc", "feat/x")
                new = f'BAR = "{bar} {bar}"\nx = 1  # {bar} done\n'
                (root / "m.py").write_text(new, encoding="utf-8")
                git(root, "add", "-A")
                args = ["m.py"]
                if base:
                    git(root, "commit", "-qm", "bar")
                    args = ["--base", base, "m.py"]
                env = {"PYTHONPATH": str(SRC), "PATH": os.environ.get("PATH", "/usr/bin:/bin")}
                env |= {"PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"}
                p = subprocess.run(
                    [
                        sys.executable,
                        *FAIL_ON_LOCALE_ENCODING,
                        "-m",
                        "dev_tooling.check_comments",
                        *args,
                    ],
                    cwd=root,
                    capture_output=True,
                    check=False,
                    env=env,
                )
                err = p.stderr.decode("cp1252", "replace")
                self.assertNotIn("Traceback", err)
                self.assertEqual(p.returncode, 1, err)
                out = p.stdout.decode("cp1252")
                self.assertNotIn("m.py:1:", out)
                self.assertIn("m.py:2:", out)


class Words(unittest.TestCase):
    def test_markers_dropped(self) -> None:
        self.assertEqual(comment_words("#  two  words"), ["two", "words"])
        self.assertEqual(comment_words("/** a\n *  b */"), ["a", "b"])
        self.assertEqual(comment_words("//! c"), ["c"])

    def test_runs_stay_inside_one_block(self) -> None:
        old = python_comments("# alpha beta\nx = 1\n# gamma delta\n")
        removed = RemovedComments(old, {1, 3})
        self.assertFalse(removed.take(["beta", "gamma"]))
        self.assertTrue(removed.take(["alpha", "beta"]))
        self.assertFalse(removed.take(["alpha"]))


if __name__ == "__main__":
    unittest.main()
