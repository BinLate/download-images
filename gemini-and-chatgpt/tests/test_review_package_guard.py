import json, tempfile, unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from review_package_guard import validate_full_package, write_manifest, verify_manifest, ReviewPackageError

SECTIONS = [
'# Independent Review Package','## Language policy','## Task identity','## Goal','## In scope','## Out of scope','## Acceptance criteria','## Material constraints and assumptions','## Implementation summary','## Planner work-item summary','## Pull request identity','## Verification evidence bound to TARGET_HEAD_SHA','## Prior blocking findings / dispositions','## Changed-file / diff context','## Reviewer contract','## Binding instruction']

def full_prompt():
    lines=['=== GEMINI_CHATGPT_REVIEW_BEGIN ===','PROMPT_ID: 0123456789abcdef01234567','TARGET_HEAD_SHA: ' + 'a'*40,'']
    for s in SECTIONS:
        lines += [s, '- evidence line', '']
    while len(lines) < 45: lines.append('filler')
    lines += ['=== GEMINI_CHATGPT_REVIEW_END ===','PROMPT_ID: 0123456789abcdef01234567','TARGET_HEAD_SHA: ' + 'a'*40]
    return '\n'.join(lines)+'\n'

class T(unittest.TestCase):
    def test_full_package_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'reviewer-prompt.txt'; p.write_text(full_prompt())
            m=write_manifest(p)
            self.assertEqual(m['canonical_lines'], len(full_prompt().rstrip('\n').split('\n')))
            self.assertEqual(verify_manifest(p)['canonical_sha256'], m['canonical_sha256'])
    def test_three_line_fake_rejected(self):
        bad='=== GEMINI_CHATGPT_REVIEW_BEGIN ===\nPROMPT_ID: 0123456789abcdef01234567\nTARGET_HEAD_SHA: '+'a'*40+'\n'
        with self.assertRaises(ReviewPackageError): validate_full_package(bad)
    def test_overwrite_after_manifest_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'reviewer-prompt.txt'; p.write_text(full_prompt()); write_manifest(p)
            p.write_text(full_prompt().replace('evidence line','changed line',1))
            with self.assertRaises(ReviewPackageError): verify_manifest(p)

if __name__=='__main__': unittest.main()
