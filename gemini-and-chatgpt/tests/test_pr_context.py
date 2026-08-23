import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pr_context.py"
HEAD = "0123456789abcdef0123456789abcdef01234567"
OTHER = "fedcba9876543210fedcba9876543210fedcba98"


class PrContextV1Tests(unittest.TestCase):
    def make_fake_bin(self, directory, git_head=HEAD, pr_head=HEAD, pr_state="OPEN"):
        fake = Path(directory)
        gh = fake / "gh"
        git = fake / "git"
        gh.write_text(textwrap.dedent(f'''\
            #!/bin/sh
            if [ "$1 $2" = "repo view" ]; then
              printf '%s\\n' '{{"nameWithOwner":"BinLate/awf-plus","url":"https://github.com/BinLate/awf-plus"}}'
              exit 0
            fi
            if [ "$1 $2" = "pr view" ]; then
              printf '%s\\n' '{{"number":7,"url":"https://github.com/BinLate/awf-plus/pull/7","headRefName":"feat/test","headRefOid":"{pr_head}","baseRefName":"main","baseRefOid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","state":"{pr_state}"}}'
              exit 0
            fi
            echo "unexpected gh call" >&2
            exit 9
        '''), encoding="utf-8")
        git.write_text(textwrap.dedent(f'''\
            #!/bin/sh
            if [ "$1 $2" = "rev-parse HEAD" ]; then
              printf '%s\\n' '{git_head}'
              exit 0
            fi
            echo "unexpected git call" >&2
            exit 9
        '''), encoding="utf-8")
        gh.chmod(0o755)
        git.chmod(0o755)
        (fake / "gh.bat").write_text(textwrap.dedent(f'''\
            @echo off
            if "%~1 %~2"=="repo view" (
              echo {{"nameWithOwner":"BinLate/awf-plus","url":"https://github.com/BinLate/awf-plus"}}
              exit /b 0
            )
            if "%~1 %~2"=="pr view" (
              echo {{"number":7,"url":"https://github.com/BinLate/awf-plus/pull/7","headRefName":"feat/test","headRefOid":"{pr_head}","baseRefName":"main","baseRefOid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","state":"{pr_state}"}}
              exit /b 0
            )
            echo unexpected gh call >&2
            exit /b 9
        '''), encoding="utf-8")
        (fake / "git.bat").write_text(textwrap.dedent(f'''\
            @echo off
            if "%~1 %~2"=="rev-parse HEAD" (
              echo {git_head}
              exit /b 0
            )
            echo unexpected git call >&2
            exit /b 9
        '''), encoding="utf-8")

    def run_cli(self, fake_bin, state_path):
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env.get("PATH", "")
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--write", str(state_path)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def test_writes_pr_identity_when_local_and_pr_head_match(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fake = td / "bin"
            fake.mkdir()
            self.make_fake_bin(fake)
            state = td / ".ai" / "review-state.json"
            proc = self.run_cli(fake, state)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(state.read_text(encoding="utf-8"))
            self.assertEqual(payload["repository"], "BinLate/awf-plus")
            self.assertEqual(payload["pr_number"], 7)
            self.assertEqual(payload["pr_state"], "OPEN")
            self.assertEqual(payload["head_sha"], HEAD)
            self.assertEqual(payload["review_round"], 0)
            self.assertEqual(payload["max_review_rounds"], 5)

    def test_rejects_local_head_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fake = td / "bin"
            fake.mkdir()
            self.make_fake_bin(fake, git_head=OTHER, pr_head=HEAD)
            state = td / "review-state.json"
            proc = self.run_cli(fake, state)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("does not match PR HEAD", proc.stderr)
            self.assertFalse(state.exists())

    def test_rejects_non_open_pr(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            fake = td / "bin"
            fake.mkdir()
            self.make_fake_bin(fake, pr_state="CLOSED")
            state = td / "review-state.json"
            proc = self.run_cli(fake, state)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("must be OPEN", proc.stderr)
            self.assertFalse(state.exists())


if __name__ == "__main__":
    unittest.main()
