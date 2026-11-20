"""Branch, PR title and PR body conventions: python3 -m unittest tests/test_check_git.py"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dev_tooling.check_git import (
    DEFAULTS,
    GitConfig,
    body_problems,
    branch_problem,
    mixed_change_problem,
    title_problem,
)

CFG = GitConfig(**DEFAULTS)  # type: ignore[arg-type]
TEMPLATE = (
    Path(__file__).resolve().parent.parent / "lint/github/.github/pull_request_template.md"
).read_text()


def filled(evidence: str = "colcon test: 42 passed", risk: str = "Low") -> str:
    body = TEMPLATE.replace("## Evidence\n", f"## Evidence\n{evidence}\n", 1)
    return body.replace(f"- [ ] **{risk}**", f"- [x] **{risk}**", 1)


class Branches(unittest.TestCase):
    def test_good_names(self) -> None:
        for name in [
            "feat/motor-current-limit",
            "fix/123-imu-timestamp",
            "feature/charge-attack",
            "chore/bump-typst",
            "claude/fix-lint-AbC12",
            "dependabot/cargo/serde-1.0",
        ]:
            self.assertIsNone(branch_problem(name, CFG), name)

    def test_bad_names(self) -> None:
        for name in ["my-branch", "Feat/Thing", "feat/Thing", "wip", "feat/", "feat/two words"]:
            self.assertIsNotNone(branch_problem(name, CFG), name)

    def test_protected(self) -> None:
        problem = branch_problem("main", CFG)
        self.assertIsNotNone(problem)
        self.assertIn("git switch -c", problem or "")


class Titles(unittest.TestCase):
    def test_good_titles(self) -> None:
        for t in [
            "fix(imu): use sensor timestamp for fusion",
            "feat!: drop ROS 2 Humble support",
            "chore(lint): ban HAL_Delay outside init",
            "docs: add feature map",
        ]:
            self.assertIsNone(title_problem(t, CFG), t)

    def test_bad_titles(self) -> None:
        for t in [
            "Fix the IMU",
            "fix:missing space",
            "feature: not a commit type",
            "fix(IMU): caps scope",
            "",
        ]:
            self.assertIsNotNone(title_problem(t, CFG), t)

    def test_too_long(self) -> None:
        self.assertIn("characters", title_problem("fix: " + "x" * 80, CFG) or "")


class Bodies(unittest.TestCase):
    def test_untouched_template_fails_both(self) -> None:
        problems = body_problems(TEMPLATE, CFG)
        self.assertEqual(len(problems), 2)

    def test_filled_template_passes(self) -> None:
        self.assertEqual(body_problems(filled(), CFG), [])

    def test_two_risk_boxes_fail(self) -> None:
        body = filled().replace("- [ ] **Medium**", "- [x] **Medium**", 1)
        self.assertEqual(len(body_problems(body, CFG)), 1)

    def test_evidence_only_in_html_comment_fails(self) -> None:
        body = filled(evidence="<!-- tests pass -->")
        self.assertIn("Evidence", body_problems(body, CFG)[0])


class MixedChanges(unittest.TestCase):
    def test_config_with_code_flagged(self) -> None:
        self.assertIsNotNone(mixed_change_problem(["patterns.toml", "src/motor.c"], CFG))
        self.assertIsNotNone(mixed_change_problem([".github/workflows/ci.yml", "src/a.rs"], CFG))

    def test_config_alone_or_code_alone_ok(self) -> None:
        self.assertIsNone(mixed_change_problem(["patterns.toml", ".clang-tidy"], CFG))
        self.assertIsNone(mixed_change_problem(["src/motor.c", "docs/FEATURE_MAP.md"], CFG))


HOOK = "import sys; from dev_tooling.check_git import main_branch; sys.exit(main_branch())"


class PushToMain(unittest.TestCase):
    def test_hook_blocks_main_and_bad_names(self) -> None:
        src = Path(__file__).resolve().parent.parent / "src"
        with tempfile.TemporaryDirectory() as d:
            git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
            subprocess.run([*git, "init", "-q", "-b", "main"], cwd=d, check=True)
            subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "x"], cwd=d, check=True)

            def run(env_branch: str = "") -> subprocess.CompletedProcess[str]:
                env = {"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin:/usr/local/bin"}
                if env_branch:
                    env["PRE_COMMIT_REMOTE_BRANCH"] = f"refs/heads/{env_branch}"
                return subprocess.run(
                    [sys.executable, "-c", HOOK],
                    cwd=d,
                    capture_output=True,
                    text=True,
                    check=False,
                    env=env,
                )

            self.assertEqual(run().returncode, 1)
            subprocess.run([*git, "switch", "-q", "-c", "feat/ok-name"], cwd=d, check=True)
            self.assertEqual(run().returncode, 0)
            self.assertEqual(run(env_branch="main").returncode, 1)


if __name__ == "__main__":
    unittest.main()
