"""dev-check runner: python3 -m unittest tests/test_check.py"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
FAIL_ON_LOCALE_ENCODING = ["-X", "warn_default_encoding", "-W", "error::EncodingWarning"]


def make_repo(d: Path, steps: str) -> None:
    subprocess.run([*GIT, "init", "-q", "-b", "main"], cwd=d, check=True)
    (d / "a.txt").write_text("base\n")
    (d / "patterns.toml").write_text(textwrap.dedent(steps), encoding="utf-8")
    subprocess.run([*GIT, "add", "-A"], cwd=d, check=True)
    subprocess.run([*GIT, "commit", "-qm", "base"], cwd=d, check=True)


def dev_check(d: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": str(SRC)}
    return subprocess.run(
        [sys.executable, "-m", "dev_tooling.check", *args],
        cwd=d,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


STEPS = """
    [[check.step]]
    name = "ok"
    run = "echo '42 passed in 0.1s'"
    summary = '(\\d+ passed)'

    [[check.step]]
    name = "broken"
    run = "echo 'noise'; echo 'src/a.c:3: error: bad thing'; echo 'more noise'; exit 1"

    [[check.step]]
    name = "slow"
    run = "echo done"
    slow = true

    [[check.step]]
    name = "missing-tool"
    run = "nonexistent-tool-xyz"
    needs = ["nonexistent-tool-xyz"]

    [[check.step]]
    name = "on-changed"
    run = "echo files: {changed}"
    summary = 'files: (.*)'

    [[check.step]]
    name = "needs-dir"
    run = "echo hi"
    requires_path = "build-host"
"""


class DevCheck(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        make_repo(self.d, STEPS)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def line(self, out: str, name: str) -> str:
        return next(ln for ln in out.splitlines() if f"  {name} " in ln or ln.endswith(f"  {name}"))

    def test_summary_lines_and_exit_code(self) -> None:
        p = dev_check(self.d)
        self.assertEqual(p.returncode, 1)
        self.assertTrue(self.line(p.stdout, "ok").startswith("PASS"))
        self.assertIn("42 passed", self.line(p.stdout, "ok"))
        self.assertTrue(self.line(p.stdout, "broken").startswith("FAIL"))
        self.assertIn("src/a.c:3: error: bad thing", p.stdout)
        self.assertNotIn("more noise", p.stdout)
        self.assertIn("full log: .dev-check/broken.log", p.stdout)
        self.assertIn("more noise", (self.d / ".dev-check/broken.log").read_text())

    def test_skips(self) -> None:
        p = dev_check(self.d)
        self.assertIn("needs nonexistent-tool-xyz", self.line(p.stdout, "missing-tool"))
        self.assertIn("build-host not found", self.line(p.stdout, "needs-dir"))
        self.assertIn("nothing changed", self.line(p.stdout, "on-changed"))

    def test_changed_files_expand(self) -> None:
        (self.d / "a.txt").write_text("edited\n")
        (self.d / "new file.txt").write_text("untracked\n")
        p = dev_check(self.d, "--only", "on-changed")
        self.assertEqual(p.returncode, 0)
        self.assertIn("a.txt", p.stdout)
        self.assertIn("new file.txt", p.stdout)

    def test_branch_changes_count_as_changed(self) -> None:
        subprocess.run([*GIT, "switch", "-q", "-c", "feat/x"], cwd=self.d, check=True)
        (self.d / "b.txt").write_text("committed on branch\n")
        subprocess.run([*GIT, "add", "-A"], cwd=self.d, check=True)
        subprocess.run([*GIT, "commit", "-qm", "b"], cwd=self.d, check=True)
        p = dev_check(self.d, "--only", "on-changed")
        self.assertIn("b.txt", p.stdout)

    def test_colour_codes_are_stripped(self) -> None:
        red, bold, off = "\\\\033[91m", "\\\\033[1m", "\\\\033[0m"
        run = f"printf '{red}error{off} src/a.ts:3 bad\\\\n- {bold}1 error{off}\\\\n'; exit 1"
        steps = f"""
            [[check.step]]
            name = "coloured"
            run = "{run}"
            errors = '^error '
            summary = '^- (\\d+ errors?)'
        """
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            make_repo(d, steps)
            p = dev_check(d)
            self.assertIn("FAIL  coloured", p.stdout)
            self.assertTrue(self.line(p.stdout, "coloured").endswith("  1 error"))
            self.assertIn("      error src/a.ts:3 bad", p.stdout)
            self.assertNotIn("\x1b", p.stdout)
            self.assertNotIn("\x1b", (d / ".dev-check/coloured.log").read_text())

    def test_base_is_the_remote_default_branch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            remote, clone = Path(tmp) / "remote.git", Path(tmp) / "clone"
            seed = Path(tmp) / "seed"
            seed.mkdir()
            subprocess.run([*GIT, "init", "-q", "-b", "master"], cwd=seed, check=True)
            (seed / "patterns.toml").write_text(textwrap.dedent(STEPS))
            subprocess.run([*GIT, "add", "-A"], cwd=seed, check=True)
            subprocess.run([*GIT, "commit", "-qm", "base"], cwd=seed, check=True)
            subprocess.run([*GIT, "clone", "-q", "--bare", str(seed), str(remote)], check=True)
            subprocess.run([*GIT, "clone", "-q", str(remote), str(clone)], check=True)
            subprocess.run([*GIT, "switch", "-q", "-c", "feat/x"], cwd=clone, check=True)
            (clone / "b.txt").write_text("committed on branch\n")
            subprocess.run([*GIT, "add", "-A"], cwd=clone, check=True)
            subprocess.run([*GIT, "commit", "-qm", "b"], cwd=clone, check=True)
            p = dev_check(clone, "--only", "on-changed")
            self.assertIn("b.txt", p.stdout)

    def test_non_ascii_output_with_a_non_utf8_locale(self) -> None:
        steps = """
            [[check.step]]
            name = "unicode"
            run = "echo 'naïve ✓ error: bad µs'; exit 1"
        """
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            make_repo(d, steps)
            env = {**os.environ, "PYTHONPATH": str(SRC), "PYTHONUTF8": "0"}
            env["PYTHONIOENCODING"] = "cp1252"
            p = subprocess.run(
                [sys.executable, *FAIL_ON_LOCALE_ENCODING, "-m", "dev_tooling.check"],
                cwd=d,
                capture_output=True,
                check=False,
                env=env,
            )
            out = p.stdout.decode("cp1252")
            self.assertEqual(p.returncode, 1, p.stderr.decode("cp1252", "replace"))
            self.assertIn("FAIL  unicode", out)
            self.assertIn("naïve ? error: bad µs", out)
            log = (d / ".dev-check/unicode.log").read_text(encoding="utf-8")
            self.assertIn("naïve ✓ error: bad µs", log)

    def test_changed_files_are_restored_after_a_step_rewrites_them(self) -> None:
        steps = """
            [[check.step]]
            name = "fixer"
            run = "for f in {changed}; do printf 'fixed\\\\n' > \\"$f\\"; done; exit 1"

            [[check.step]]
            name = "quiet-fixer"
            run = "for f in {changed}; do printf 'fixed' > \\"$f\\"; done"

            [[check.step]]
            name = "reader"
            run = "cat {changed}"
        """
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            make_repo(d, steps)
            mine = b"my edit, not staged  \r\nno newline at end"
            (d / "a.txt").write_bytes(mine)
            (d / "new.txt").write_bytes(b"untracked\n\n\n")
            p = dev_check(d)
            self.assertEqual((d / "a.txt").read_bytes(), mine)
            self.assertEqual((d / "new.txt").read_bytes(), b"untracked\n\n\n")
            self.assertTrue(self.line(p.stdout, "fixer").endswith("would change 2 file(s)"))
            self.assertIn("      would change a.txt", p.stdout)
            self.assertIn("      would change new.txt", p.stdout)
            self.assertTrue(self.line(p.stdout, "quiet-fixer").startswith("FAIL"))
            self.assertTrue(self.line(p.stdout, "reader").startswith("PASS"))
            log = (d / ".dev-check/fixer.log").read_text(encoding="utf-8")
            self.assertIn("dev-check: restored a.txt", log)

    def test_quick_skips_slow(self) -> None:
        p = dev_check(self.d, "--quick")
        self.assertIn("slow (--quick)", self.line(p.stdout, "slow"))

    def test_only_and_unknown(self) -> None:
        self.assertEqual(dev_check(self.d, "--only", "ok").returncode, 0)
        p = dev_check(self.d, "--only", "nope")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("unknown step", p.stderr)

    def test_list(self) -> None:
        p = dev_check(self.d, "--list")
        self.assertEqual(p.returncode, 0)
        self.assertIn("(slow)", p.stdout)


if __name__ == "__main__":
    unittest.main()
