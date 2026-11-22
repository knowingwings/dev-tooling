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
    automerge_reasons,
    body_problems,
    branch_problem,
    checks_state,
    mixed_change_problem,
    title_problem,
    unmerged_commits,
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


class RequestedBy(unittest.TestCase):
    def test_bot_pr_needs_requested_by(self) -> None:
        problems = body_problems(filled(), CFG, author="kw-builder[bot]")
        self.assertTrue(any("Requested-by" in p for p in problems))

    def test_bot_pr_with_requested_by_passes(self) -> None:
        body = filled() + "\nRequested-by: @knowingwings\n"
        self.assertEqual(body_problems(body, CFG, author="kw-builder[bot]"), [])

    def test_humans_and_dependabot_exempt(self) -> None:
        self.assertEqual(body_problems(filled(), CFG, author="knowingwings"), [])
        self.assertEqual(body_problems(filled(), CFG, author="dependabot[bot]"), [])

    def test_requested_by_in_comment_does_not_count(self) -> None:
        body = filled() + "\n<!-- Requested-by: @knowingwings -->\n"
        self.assertTrue(body_problems(body, CFG, author="kw-builder[bot]"))


class MixedChanges(unittest.TestCase):
    def test_config_with_code_flagged(self) -> None:
        self.assertIsNotNone(mixed_change_problem(["patterns.toml", "src/motor.c"], CFG))
        self.assertIsNotNone(mixed_change_problem([".github/workflows/ci.yml", "src/a.rs"], CFG))

    def test_agent_instructions_are_protected(self) -> None:
        self.assertIsNotNone(mixed_change_problem([".claude/agents/reviewer.md", "src/a.c"], CFG))
        self.assertIsNotNone(mixed_change_problem(["docs/agents/builder.md", "src/a.c"], CFG))

    def test_config_alone_or_code_alone_ok(self) -> None:
        self.assertIsNone(mixed_change_problem(["patterns.toml", ".clang-tidy"], CFG))
        self.assertIsNone(mixed_change_problem(["src/motor.c", "docs/FEATURE_MAP.md"], CFG))

    def test_kit_adoption_or_update_may_mix(self) -> None:
        adoption = [".dev-tooling-version", "AGENTS.md", ".github/CODEOWNERS", "check", "README.md"]
        self.assertIsNone(mixed_change_problem(adoption, CFG))

    def test_kit_version_file_is_protected(self) -> None:
        self.assertIsNotNone(mixed_change_problem(["patterns.toml", "src/motor.c"], CFG))
        self.assertIn(".dev-tooling-version", CFG.protected_paths)


ON = GitConfig(**{**DEFAULTS, "automerge": True})  # type: ignore[arg-type]


def review(user: str, state: str) -> dict[str, object]:
    return {"user": {"login": user}, "state": state}


APPROVED = [review("kw-reviewer[bot]", "APPROVED")]


class AutoMerge(unittest.TestCase):
    def reasons(self, **kw: object) -> list[str]:
        args: dict[str, object] = {
            "body": filled(risk="Low"),
            "labels": [],
            "changed": ["src/motor.c"],
            "reviews": APPROVED,
            "author": "kw-builder[bot]",
            "cfg": ON,
        }
        args.update(kw)
        return automerge_reasons(**args)  # type: ignore[arg-type]

    def test_low_risk_approved_code_change_merges(self) -> None:
        self.assertEqual(self.reasons(), [])

    def test_off_by_default(self) -> None:
        self.assertIn("off", self.reasons(cfg=CFG)[0])

    def test_medium_and_high_wait_for_a_human(self) -> None:
        self.assertIn("risk is Medium", self.reasons(body=filled(risk="Medium"))[0])
        self.assertIn("risk is High", self.reasons(body=filled(risk="High"))[0])

    def test_unticked_risk(self) -> None:
        self.assertIn("not set", self.reasons(body=TEMPLATE)[0])

    def test_kit_update_waits_for_a_human(self) -> None:
        reasons = self.reasons(changed=[".dev-tooling-version", "README.md"])
        self.assertIn("changes the checks themselves (.dev-tooling-version)", reasons[0])

    def test_needs_approval_from_someone_else(self) -> None:
        self.assertIn("no approval", self.reasons(reviews=[])[0])
        self_approved = [review("kw-builder[bot]", "APPROVED")]
        self.assertIn("no approval", self.reasons(reviews=self_approved)[0])

    def test_latest_review_wins(self) -> None:
        later_block = [*APPROVED, review("kw-reviewer[bot]", "CHANGES_REQUESTED")]
        self.assertIn("changes requested", self.reasons(reviews=later_block)[0])
        later_ok = [review("knowingwings", "CHANGES_REQUESTED"), review("knowingwings", "APPROVED")]
        self.assertEqual(self.reasons(reviews=later_ok), [])

    def test_hold_label(self) -> None:
        self.assertIn("do-not-merge", self.reasons(labels=["do-not-merge"])[0])

    def test_check_changes_always_need_a_human(self) -> None:
        reasons = self.reasons(changed=["patterns.toml"])
        self.assertIn("checks themselves", reasons[0])


def run(
    name: str, status: str = "completed", conclusion: str | None = "success"
) -> dict[str, object]:
    return {"name": name, "status": status, "conclusion": conclusion}


GREEN = [run("conventions"), run("auto-merge", "in_progress", None)]


class WaitForChecks(unittest.TestCase):
    def test_every_other_check_green_passes(self) -> None:
        statuses = [{"context": "Cloudflare Pages", "state": "success"}]
        self.assertEqual(checks_state(GREEN, statuses, "auto-merge"), ("passed", []))

    def test_skipped_and_neutral_pass(self) -> None:
        runs = [*GREEN, run("docs", conclusion="skipped"), run("lint", conclusion="neutral")]
        self.assertEqual(checks_state(runs, [], "auto-merge")[0], "passed")

    def test_running_check_waits(self) -> None:
        runs = [*GREEN, run("test", "in_progress", None)]
        self.assertEqual(checks_state(runs, [], "auto-merge"), ("pending", ["test"]))

    def test_pending_status_waits(self) -> None:
        statuses = [{"context": "Cloudflare Pages", "state": "pending"}]
        self.assertEqual(checks_state(GREEN, statuses, "auto-merge")[0], "pending")

    def test_failed_check_or_status_never_merges(self) -> None:
        failed = [*GREEN, run("test", conclusion="failure")]
        self.assertEqual(checks_state(failed, [], "auto-merge"), ("failed", ["test (failure)"]))
        error = [{"context": "ci/build", "state": "error"}]
        self.assertEqual(checks_state(GREEN, error, "auto-merge")[0], "failed")

    def test_own_runs_ignored_even_cancelled(self) -> None:
        runs = [*GREEN, run("auto-merge", conclusion="cancelled")]
        self.assertEqual(checks_state(runs, [], "auto-merge")[0], "passed")

    def test_no_other_check_yet_waits(self) -> None:
        only_self = [run("auto-merge", "in_progress", None)]
        self.assertEqual(checks_state(only_self, [], "auto-merge")[0], "pending")


FAKE_GH = """#!/bin/sh
case "$2" in
  */status) echo '{"statuses": []}' ;;
  *) n=$(cat "$STATE"); echo $((n + 1)) > "$STATE"
     if [ "$n" -lt 1 ]; then s=in_progress c=null; else s=completed c='"'$FINAL'"'; fi
     echo '{"check_runs": [{"name": "test", "status": "'$s'", "conclusion": '$c'}]}' ;;
esac
"""


class WaitForChecksCommand(unittest.TestCase):
    """Runs wait-for-checks against a fake gh: the check is running at first, then finishes."""

    def wait(self, final: str) -> subprocess.CompletedProcess[str]:
        src = Path(__file__).resolve().parent.parent / "src"
        cli = "import sys; from dev_tooling.check_git import main_wait; sys.exit(main_wait())"
        with tempfile.TemporaryDirectory() as d:
            gh = Path(d) / "gh"
            gh.write_text(FAKE_GH)
            gh.chmod(0o755)
            (Path(d) / "state").write_text("0")
            args = ["--repo", "o/r", "--sha", "abc1234", "--ignore", "auto-merge"]
            return subprocess.run(
                [sys.executable, "-c", cli, *args, "--grace", "0", "--interval", "0"],
                capture_output=True,
                text=True,
                check=False,
                env={
                    "PYTHONPATH": str(src),
                    "PATH": f"{d}:/usr/bin:/bin",
                    "STATE": str(Path(d) / "state"),
                    "FINAL": final,
                },
            )

    def test_waits_then_passes(self) -> None:
        p = self.wait("success")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("every other check on abc1234 passed", p.stdout)

    def test_waits_then_refuses_a_failure(self) -> None:
        p = self.wait("failure")
        self.assertEqual(p.returncode, 1)
        self.assertIn("not merging abc1234: test (failure) failed", p.stdout)


def pr(merged: bool = True, base: str = "main") -> dict[str, object]:
    return {
        "number": 7,
        "merged_at": "2026-11-22T10:00:00Z" if merged else None,
        "base": {"ref": base},
    }


class MainGuard(unittest.TestCase):
    def test_commit_from_a_merged_pr_is_fine(self) -> None:
        self.assertEqual(unmerged_commits([{"sha": "a1", "pulls": [pr()]}], "main"), [])

    def test_direct_push_is_flagged(self) -> None:
        self.assertEqual(unmerged_commits([{"sha": "b2", "pulls": []}], "main"), ["b2"])

    def test_open_pr_does_not_count(self) -> None:
        self.assertEqual(
            unmerged_commits([{"sha": "c3", "pulls": [pr(merged=False)]}], "main"), ["c3"]
        )

    def test_pr_merged_elsewhere_does_not_count(self) -> None:
        commits = [{"sha": "d4", "pulls": [pr(base="develop")]}]
        self.assertEqual(unmerged_commits(commits, "main"), ["d4"])
        self.assertEqual(unmerged_commits(commits, "develop"), [])

    def run_cli(self, **env: str) -> subprocess.CompletedProcess[str]:
        src = Path(__file__).resolve().parent.parent / "src"
        cli = "import sys; from dev_tooling.check_git import main_guard; sys.exit(main_guard())"
        return subprocess.run(
            [sys.executable, "-c", cli],
            capture_output=True,
            text=True,
            check=False,
            env={"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin", **env},
        )

    def test_command_passes_merged_commits(self) -> None:
        commits = '[{"sha": "a1", "pulls": [{"merged_at": "2026-11-22", "base": {"ref": "main"}}]}]'
        p = self.run_cli(BRANCH="main", COMMITS_JSON=commits, PUSH_FORCED="false")
        self.assertEqual(p.returncode, 0)

    def test_command_reports_direct_push_and_force_push(self) -> None:
        p = self.run_cli(
            BRANCH="main", COMMITS_JSON='[{"sha": "b2", "pulls": []}]', PUSH_FORCED="true"
        )
        self.assertEqual(p.returncode, 1)
        self.assertIn("force-push", p.stdout)
        self.assertIn("- b2 reached `main` without a pull request merged into it.", p.stdout)
        self.assertIn("open a pull request that reverts it or explains it", p.stdout)


PR_CLI = "import sys; from dev_tooling.check_git import main_pr; sys.exit(main_pr())"


class CheckPrCommand(unittest.TestCase):
    """Runs the real command the way CI does (environment variables), not just the functions."""

    def run_cli(self, **env: str) -> subprocess.CompletedProcess[str]:
        src = Path(__file__).resolve().parent.parent / "src"
        full_env = {"PYTHONPATH": str(src), "PATH": "/usr/bin:/bin:/usr/local/bin", **env}
        with tempfile.TemporaryDirectory() as d:
            return subprocess.run(
                [sys.executable, "-c", PR_CLI],
                cwd=d,
                capture_output=True,
                text=True,
                check=False,
                env=full_env,
            )

    def test_good_pr_passes(self) -> None:
        p = self.run_cli(
            PR_TITLE="fix(imu): use sensor timestamp",
            PR_BODY=filled(),
            PR_HEAD_REF="fix/imu-timestamp",
            PR_AUTHOR="knowingwings",
        )
        self.assertEqual((p.returncode, p.stderr), (0, ""))

    def test_bot_pr_without_requested_by_fails(self) -> None:
        p = self.run_cli(
            PR_TITLE="fix(imu): use sensor timestamp",
            PR_BODY=filled(),
            PR_HEAD_REF="fix/imu-timestamp",
            PR_AUTHOR="kw-builder[bot]",
        )
        self.assertEqual(p.returncode, 1)
        self.assertIn("Requested-by", p.stdout)
        self.assertEqual(p.stderr, "")


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
