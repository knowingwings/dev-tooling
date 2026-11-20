"""STE length rules: block splitting, sentence splitting and limits.

Run: python3 -m unittest tests/test_check_prose.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dev_tooling.check_prose import DEFAULTS, Config, problems

KIT = Path(__file__).resolve().parent.parent

CFG = Config(**DEFAULTS)  # type: ignore[arg-type]
LONG = " ".join(["word"] * 26) + "."
STEP = " ".join(["word"] * 21) + "."


def rules(src: str, *, typst: bool = False) -> list[str]:
    return [r for _, _, r, _ in problems(src, typst, CFG)]


class Markdown(unittest.TestCase):
    def test_short_sentences_pass(self) -> None:
        self.assertEqual(rules("One short sentence. Another one, e.g. with an abbreviation.\n"), [])

    def test_long_sentence(self) -> None:
        self.assertEqual(rules(LONG + "\n"), ["sentence-too-long"])

    def test_sentence_over_two_lines_is_one_sentence(self) -> None:
        half = " ".join(["word"] * 13)
        self.assertEqual(rules(f"{half}\n{half}.\n"), ["sentence-too-long"])

    def test_numbered_step_uses_procedure_limit(self) -> None:
        self.assertEqual(rules(f"1. {STEP}\n"), ["step-too-long"])

    def test_bullet_uses_descriptive_limit(self) -> None:
        self.assertEqual(rules(f"- {STEP}\n"), [])

    def test_paragraph_too_long(self) -> None:
        self.assertEqual(rules("A. B. C. D. E. F. G.\n"), ["paragraph-too-long"])

    def test_list_items_are_not_one_paragraph(self) -> None:
        self.assertEqual(rules("".join(f"- Item {i}.\n" for i in range(8))), [])

    def test_code_heading_table_and_html_ignored(self) -> None:
        src = f"# {LONG}\n\n```\n{LONG}\n```\n\n| {LONG} |\n\n<p>{LONG}</p>\n"
        self.assertEqual(rules(src), [])

    def test_inline_code_counts_as_one_word(self) -> None:
        code = "`" + " ".join(["x"] * 30) + "`"
        self.assertEqual(rules(f"Run {code} now.\n"), [])

    def test_link_url_not_counted(self) -> None:
        self.assertEqual(rules("See [the guide](https://example.com/a.b.c/d e f g h i j k).\n"), [])

    def test_front_matter_ignored(self) -> None:
        self.assertEqual(rules(f"---\ntitle: {LONG}\n---\nShort.\n"), [])

    def test_allow_with_reason(self) -> None:
        src = f"<!-- lint-allow(prose): quoted text from a standard -->\n{LONG}\n"
        self.assertEqual(rules(src), [])

    def test_allow_needs_reason(self) -> None:
        self.assertEqual(rules(f"<!-- lint-allow(prose): x -->\n{LONG}\n"), ["sentence-too-long"])


class Typst(unittest.TestCase):
    def test_code_and_headings_ignored(self) -> None:
        src = f'#set text(font: "Inter")\n= {LONG}\n// {LONG}\n\nShort text.\n'
        self.assertEqual(rules(src, typst=True), [])

    def test_numbered_item_is_a_step(self) -> None:
        self.assertEqual(rules(f"+ {STEP}\n", typst=True), ["step-too-long"])

    def test_markup_stripped(self) -> None:
        self.assertEqual(rules("See @fig:block and #emph[this] with $x + y$.\n", typst=True), [])

    def test_long_sentence(self) -> None:
        self.assertEqual(rules(LONG + "\n", typst=True), ["sentence-too-long"])


class ChangedBlocksOnly(unittest.TestCase):
    def test_existing_problem_not_reported_new_one_is(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "docs").mkdir()
            doc = root / "docs" / "guide.md"
            doc.write_text(f"{LONG}\n\nShort.\n")
            git = ["git", "-C", d, "-c", "user.name=t", "-c", "user.email=t@t"]
            subprocess.run([*git, "init", "-q"], check=True)
            subprocess.run([*git, "add", "-A"], check=True)
            subprocess.run([*git, "commit", "-qm", "init"], check=True)
            cmd = [sys.executable, "-m", "dev_tooling.check_prose", "--root", d, "docs/guide.md"]
            env = {"PYTHONPATH": str(KIT / "src"), "PATH": "/usr/bin:/bin"}

            doc.write_text(f"{LONG}\n\nShort, and now changed.\n")
            subprocess.run([*git, "add", "-A"], check=True)
            p = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
            self.assertEqual(p.returncode, 0, p.stdout)

            doc.write_text(f"{LONG}\n\nShort, and now changed. {LONG}\n")
            subprocess.run([*git, "add", "-A"], check=True)
            p = subprocess.run(cmd, capture_output=True, text=True, env=env, check=False)
            self.assertEqual(p.returncode, 1)
            self.assertIn("docs/guide.md:3: [sentence-too-long]", p.stdout)


if __name__ == "__main__":
    unittest.main()
