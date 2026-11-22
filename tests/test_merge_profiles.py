"""Merging two profiles' copies of a kit file: python3 -m unittest tests/test_merge_profiles.py"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dev_tooling.merge_profiles import (
    join_patterns,
    jsonc_comments,
    merge,
    merge_patterns,
    merge_precommit,
    merge_vscode,
    strip_jsonc,
)

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore[no-redef]

KIT = Path(__file__).resolve().parent.parent
LINT = KIT / "lint"
VSCODE = KIT / "vscode"


def kit(path: str) -> str:
    return (KIT / path).read_text()


def hook_ids(config: str) -> list[str]:
    return re.findall(r"^      - id:\s*(\S+)", config, re.M)


class PreCommit(unittest.TestCase):
    def setUp(self) -> None:
        self.merged = merge_precommit(
            kit("lint/astro/.pre-commit-config.yaml"), kit("lint/typst/.pre-commit-config.yaml")
        )

    def test_every_hook_from_both(self) -> None:
        ids = hook_ids(self.merged)
        for hook in ("prettier", "eslint", "astro-check", "typstyle", "typst-compile", "typos"):
            self.assertIn(hook, ids)
        self.assertEqual(len(ids), len(set(ids)))

    def test_shared_hook_keeps_first_settings_and_joins_files(self) -> None:
        self.assertIn("args: [--maxkb=2048]", self.merged)
        self.assertNotIn("--maxkb=4096", self.merged)
        typos = self.merged.split("id: typos", 1)[1].split("\n  - repo:", 1)[0]
        files = re.search(r"files:\s*(\S+)", typos)
        assert files is not None
        self.assertRegex("guide.mdx", files.group(1))
        self.assertRegex("cv.typ", files.group(1))

    def test_exclude_patterns_joined(self) -> None:
        exclude = re.search(r"^exclude:\s*(\S+)", self.merged, re.M)
        assert exclude is not None
        for path in ("dist/index.html", "node_modules/x.js", "build/cv.pdf"):
            self.assertRegex(path, exclude.group(1))

    def test_one_repo_block_per_url(self) -> None:
        urls = re.findall(r"^  - repo:\s*(\S+)", self.merged, re.M)
        self.assertEqual(len(urls), len(set(urls)))

    def test_identical_input_unchanged(self) -> None:
        astro = kit("lint/astro/.pre-commit-config.yaml")
        self.assertEqual(merge_precommit(astro, astro), astro)


class Patterns(unittest.TestCase):
    def test_new_steps_after_the_first_profiles(self) -> None:
        merged = merge_patterns(kit("lint/astro/patterns.toml"), kit("lint/typst/patterns.toml"))
        names = [s["name"] for s in tomllib.loads(merged)["check"]["step"]]
        self.assertEqual(names, ["hooks", "eslint", "prettier", "astro-check", "build", "compile"])

    def test_rules_added_by_id_and_tables_kept(self) -> None:
        first, second = kit("lint/python/patterns.toml"), kit("lint/ros2/patterns.toml")
        data = tomllib.loads(merge_patterns(first, second))
        ros2 = tomllib.loads(second)
        self.assertEqual(
            sorted(r["id"] for r in data["rule"]), sorted(r["id"] for r in ros2["rule"])
        )
        self.assertEqual(data["comments"], tomllib.loads(first)["comments"])

    def test_identical_input_unchanged(self) -> None:
        typst = kit("lint/typst/patterns.toml")
        self.assertEqual(tomllib.loads(merge_patterns(typst, typst)), tomllib.loads(typst))


class VSCode(unittest.TestCase):
    def load(self, name: str, first: str = "astro", second: str = "typst") -> dict[str, object]:
        out = merge_vscode(
            name,
            (VSCODE / first / ".vscode" / name).read_text(),
            (VSCODE / second / ".vscode" / name).read_text(),
        )
        return json.loads(strip_jsonc(out))

    def test_extensions_union(self) -> None:
        recs = self.load("extensions.json")["recommendations"]
        assert isinstance(recs, list)
        self.assertIn("astro-build.astro-vscode", recs)
        self.assertIn("myriad-dreamin.tinymist", recs)
        self.assertEqual(len(recs), len(set(recs)))

    def test_settings_merge_nested_objects(self) -> None:
        settings = self.load("settings.json")
        self.assertEqual(settings["editor.defaultFormatter"], "esbenp.prettier-vscode")
        self.assertIn("[typst]", settings)
        self.assertEqual(settings["files.exclude"], {"dist": True, ".astro": True, "build": True})

    def test_one_default_build_task(self) -> None:
        tasks = self.load("tasks.json")["tasks"]
        assert isinstance(tasks, list)
        defaults = [t["label"] for t in tasks if t.get("group", {}).get("isDefault")]
        self.assertEqual(defaults, ["check: every step (./check)"])
        self.assertIn("typst: compile all (pinned, reproducible)", [t["label"] for t in tasks])

    def test_launch_configurations_by_name(self) -> None:
        launch = self.load("launch.json", "python", "rust")["configurations"]
        assert isinstance(launch, list)
        names = [c["name"] for c in launch]
        self.assertEqual(len(names), len(set(names)))

    def test_leading_comments_kept(self) -> None:
        out = merge_vscode(
            "settings.json",
            (VSCODE / "astro/.vscode/settings.json").read_text(),
            (VSCODE / "typst/.vscode/settings.json").read_text(),
        )
        self.assertTrue(out.startswith("// Astro site."))
        self.assertIn("// Typst documents.", out)


def vscode(profile: str, name: str) -> str:
    return (VSCODE / profile / ".vscode" / name).read_text()


def line_before(text: str, needle: str) -> str:
    lines = text.splitlines()
    return next(lines[i - 1].strip() for i, ln in enumerate(lines) if needle in ln)


class VSCodeComments(unittest.TestCase):
    def test_comments_stay_before_their_keys(self) -> None:
        out = merge_vscode(
            "settings.json", vscode("astro", "settings.json"), vscode("typst", "settings.json")
        )
        self.assertEqual(
            line_before(out, '"typescript.tsdk"'),
            "// The project's TypeScript, so the editor and astro check agree.",
        )
        self.assertTrue(line_before(out, '"tinymist.systemFonts"').startswith("// Same fonts as"))

    def test_comment_before_an_array_element(self) -> None:
        out = merge_vscode(
            "settings.json", vscode("typst", "settings.json"), vscode("firmware", "settings.json")
        )
        self.assertTrue(line_before(out, '"--query-driver=').startswith("// Lets clangd ask"))

    def test_comment_dropped_with_the_array_it_was_in(self) -> None:
        out = merge_vscode(
            "settings.json", vscode("ros2", "settings.json"), vscode("firmware", "settings.json")
        )
        self.assertNotIn("--query-driver", out)
        self.assertNotIn("Lets clangd ask", out)
        self.assertTrue(line_before(out, '"clangd.arguments"').startswith("// clangd reads"))

    def test_first_profiles_comments_all_kept(self) -> None:
        profiles = sorted(p.name for p in VSCODE.iterdir() if (p / ".vscode").is_dir())
        for name in ("settings.json", "tasks.json", "launch.json", "extensions.json"):
            for first in profiles:
                for second in profiles:
                    a, b = VSCODE / first / ".vscode" / name, VSCODE / second / ".vscode" / name
                    if first == second or not (a.exists() and b.exists()):
                        continue
                    out = merge_vscode(name, a.read_text(), b.read_text())
                    for ln in a.read_text().splitlines():
                        if ln.strip().startswith("//"):
                            self.assertIn(ln.strip(), out, f"{first},{second} {name}")
                    json.loads(strip_jsonc(out))

    def test_without_comments_same_as_json_dumps(self) -> None:
        first, second = '{"a": [1, 2], "b": {"c": true}}', '{"b": {"d": null}, "e": "x"}'
        out = merge_vscode("settings.json", first, second)
        expected = {"a": [1, 2], "b": {"c": True, "d": None}, "e": "x"}
        self.assertEqual(out, json.dumps(expected, indent=2) + "\n")

    def test_comment_paths(self) -> None:
        text = (
            '{\n  // a\n  "x": [\n    1,\n    // b\n    "two"\n  ],\n'
            '  "y": {"z": 1 /* c */}\n  // d\n}\n'
        )
        self.assertEqual(
            jsonc_comments(text),
            {("x",): ["// a"], ("x", 1): ["// b"], ("y",): ["/* c */"], (): ["// d"]},
        )


class Jsonc(unittest.TestCase):
    def test_comments_and_trailing_commas(self) -> None:
        text = '// top\n{\n  "a": "http://x//y", /* inline */ "b": [1, 2,],\n}\n'
        self.assertEqual(json.loads(strip_jsonc(text)), {"a": "http://x//y", "b": [1, 2]})

    def test_escaped_quote_in_string(self) -> None:
        self.assertEqual(
            json.loads(strip_jsonc('{"a": "say \\"hi\\" // no"}')), {"a": 'say "hi" // no'}
        )


class Dispatch(unittest.TestCase):
    def test_unsupported_file(self) -> None:
        self.assertIsNone(merge("ruff.toml", "a = 1\n", "a = 2\n"))
        self.assertIsNone(merge(".clang-tidy", "x", "y"))

    def test_join_patterns(self) -> None:
        self.assertEqual(join_patterns("a", "a"), "a")
        self.assertEqual(join_patterns("a", "b"), "(?:a)|(?:b)")


if __name__ == "__main__":
    unittest.main()
