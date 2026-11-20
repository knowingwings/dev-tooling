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


def make_repo(d: Path, steps: str) -> None:
    subprocess.run([*GIT, "init", "-q", "-b", "main"], cwd=d, check=True)
    (d / "a.txt").write_text("base\n")
    (d / "patterns.toml").write_text(textwrap.dedent(steps))
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
