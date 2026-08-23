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
HEAD1 = "1" * 40
HEAD2 = "2" * 40
BASE = "a" * 40


class ReviewExactShaTests(unittest.TestCase):
    def _fake_bin(self, root, *, pr_state="OPEN", git_head=HEAD1, pr_head=HEAD1):
        fake = Path(root)
        gh = fake / "gh"
        git = fake / "git"
        gh.write_text(textwrap.dedent(f'''\
            #!/bin/sh
            if [ "$1 $2" = "repo view" ]; then
              echo '{{"nameWithOwner":"o/r","url":"https://github.com/o/r"}}'; exit 0
            fi
            if [ "$1 $2" = "pr view" ]; then
              echo '{{"number":9,"url":"https://github.com/o/r/pull/9","headRefName":"feat/x","headRefOid":"{pr_head}","baseRefName":"main","baseRefOid":"{BASE}","state":"{pr_state}"}}'; exit 0
            fi
            exit 9
        '''), encoding="utf-8")
        git.write_text(textwrap.dedent(f'''\
            #!/bin/sh
            if [ "$1 $2" = "rev-parse HEAD" ]; then echo '{git_head}'; exit 0; fi
            exit 9
        '''), encoding="utf-8")
        gh.chmod(0o755); git.chmod(0o755)
        (fake / "gh.bat").write_text(textwrap.dedent(f'''\
            @echo off
            if "%~1 %~2"=="repo view" (
              echo {{"nameWithOwner":"o/r","url":"https://github.com/o/r"}}
              exit /b 0
            )
            if "%~1 %~2"=="pr view" (
              echo {{"number":9,"url":"https://github.com/o/r/pull/9","headRefName":"feat/x","headRefOid":"{pr_head}","baseRefName":"main","baseRefOid":"{BASE}","state":"{pr_state}"}}
              exit /b 0
            )
            exit /b 9
        '''), encoding="utf-8")
        (fake / "git.bat").write_text(textwrap.dedent(f'''\
            @echo off
            if "%~1 %~2"=="rev-parse HEAD" (
              echo {git_head}
              exit /b 0
            )
            exit /b 9
        '''), encoding="utf-8")
        return fake

    def _run(self, fake, state):
        env = os.environ.copy(); env["PATH"] = str(fake) + os.pathsep + env.get("PATH", "")
        return subprocess.run([sys.executable, str(SCRIPT), "--write", str(state)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)

    def test_closed_pr_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); fake = td / "bin"; fake.mkdir()
            self._fake_bin(fake, pr_state="MERGED")
            state = td / "review.json"
            proc = self._run(fake, state)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("must be OPEN", proc.stderr)
            self.assertFalse(state.exists())

    def test_new_head_invalidates_legacy_approval_and_targets_new_head(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); fake = td / "bin"; fake.mkdir()
            self._fake_bin(fake, git_head=HEAD2, pr_head=HEAD2)
            state = td / "review.json"
            state.write_text(json.dumps({"head_sha": HEAD1, "approval_valid": True, "current_verdict": "APPROVED_TO_MERGE", "approved_sha": HEAD1, "review_round": 1, "max_review_rounds": 5}), encoding="utf-8")
            proc = self._run(fake, state)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            payload = json.loads(state.read_text(encoding="utf-8"))
            self.assertFalse(payload["approval_valid"])
            self.assertIsNone(payload["current_verdict"])
            self.assertIsNone(payload["approved_sha"])
            self.assertEqual(payload["current_target_sha"], HEAD2)

    def test_abbreviated_pr_head_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); fake = td / "bin"; fake.mkdir()
            self._fake_bin(fake, git_head=HEAD1, pr_head=HEAD1[:8])
            proc = self._run(fake, td / "review.json")
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("exactly 40", proc.stderr)


if __name__ == "__main__":
    unittest.main()
