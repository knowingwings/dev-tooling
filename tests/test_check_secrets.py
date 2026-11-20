"""Secret detection: keys, token formats and env files.

The fake secrets are built from parts so this file doesn't trip the check itself.

Run: python3 -m unittest tests/test_check_secrets.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dev_tooling.check_secrets import problems

PEM = "-----BEGIN " + "RSA PRIVATE KEY-----"
GH = "gh" + "p_" + "a1B2" * 9
ANT = "sk-" + "ant-" + "api03-" + "x" * 30
AWS = "AK" + "IA" + "ABCDEFGHIJKLMNOP"


def rules(rel: str, text: str) -> list[str]:
    return [r for _, r, _ in problems(rel, text)]


class Tokens(unittest.TestCase):
    def test_private_key(self) -> None:
        self.assertEqual(rules("key.pem", PEM + "\nabc\n"), ["private-key"])

    def test_public_key_is_fine(self) -> None:
        self.assertEqual(rules("key.pub", "-----BEGIN PUBLIC KEY-----\n"), [])

    def test_known_tokens(self) -> None:
        for tok in (GH, ANT, AWS):
            with self.subTest(tok=tok[:6]):
                self.assertEqual(rules("src/app.py", f'TOKEN = "{tok}"\n'), ["token"])

    def test_prefix_alone_is_fine(self) -> None:
        self.assertEqual(rules("README.md", "GitHub tokens start with `ghp_`.\n"), [])

    def test_allow_with_reason(self) -> None:
        line = f'"{GH}"  # lint-allow(secret): fake token for the parser test\n'
        self.assertEqual(rules("tests/t.py", line), [])

    def test_allow_needs_reason(self) -> None:
        self.assertEqual(rules("tests/t.py", f'"{GH}"  # lint-allow(secret): x\n'), ["token"])


class EnvFiles(unittest.TestCase):
    def test_literal_secret(self) -> None:
        self.assertEqual(rules(".env", "API_KEY=abc123\n"), ["env-plain-secret"])
        self.assertEqual(
            rules("deploy/prod.env", "export DB_PASSWORD='hunter2'\n"), ["env-plain-secret"]
        )

    def test_op_reference_and_placeholders_pass(self) -> None:
        text = (
            'API_KEY="op://Private/service/credential"\n'
            "TOKEN=${CI_TOKEN}\n"
            "SECRET=<from 1Password>\n"
            "PASSWORD=\n"
            "# PASSWORD=old\n"
            "PORT=8080\n"
        )
        self.assertEqual(rules(".env", text), [])

    def test_example_files_and_non_env_files_skipped(self) -> None:
        self.assertEqual(rules(".env.example", "API_KEY=abc123\n"), [])
        self.assertEqual(rules("config.py", "API_KEY=abc123\n"), [])

    def test_env_suffix_variants(self) -> None:
        self.assertEqual(rules(".env.local", "AUTH=abc\n"), ["env-plain-secret"])


if __name__ == "__main__":
    unittest.main()
