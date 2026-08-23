import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_review_transport import TransportVerificationError, parse_identity, verify_transport  # noqa: E402


HEAD = "a" * 40
OTHER_HEAD = "b" * 40
PROMPT_ID = "0123456789abcdef01234567"
OTHER_ID = "89abcdef0123456789abcdef"


def package(body="payload", *, prompt_id=PROMPT_ID, head=HEAD):
    return "\n".join(
        [
            "=== GEMINI_CHATGPT_REVIEW_BEGIN ===",
            f"PROMPT_ID: {prompt_id}",
            f"TARGET_HEAD_SHA: {head}",
            "",
            body,
            "",
            "=== GEMINI_CHATGPT_REVIEW_END ===",
            f"PROMPT_ID: {prompt_id}",
            f"TARGET_HEAD_SHA: {head}",
            "",
        ]
    )


class ReviewTransportTests(unittest.TestCase):
    def test_exact_composer_readback_passes(self):
        identity = verify_transport(package(), package())
        self.assertEqual(identity.prompt_id, PROMPT_ID)
        self.assertEqual(identity.target_head_sha, HEAD)

    def test_windows_newlines_are_transport_equivalent(self):
        verify_transport(package(), package().replace("\n", "\r\n"))

    def test_clipboard_race_replacement_fails_closed(self):
        with self.assertRaises(TransportVerificationError):
            verify_transport(package(), "screenshot clipboard text")

    def test_partial_or_accidentally_submitted_prompt_fails(self):
        actual = package().split("=== GEMINI_CHATGPT_REVIEW_END ===")[0]
        with self.assertRaises(TransportVerificationError):
            verify_transport(package(), actual)

    def test_same_markers_but_changed_middle_fails_exact_compare(self):
        with self.assertRaises(TransportVerificationError):
            verify_transport(package("expected payload"), package("wrong payload"))

    def test_wrong_prompt_id_fails(self):
        with self.assertRaises(TransportVerificationError):
            verify_transport(package(), package(prompt_id=OTHER_ID))

    def test_wrong_head_fails(self):
        with self.assertRaises(TransportVerificationError):
            verify_transport(package(), package(head=OTHER_HEAD))

    def test_identity_requires_two_matching_heads(self):
        malformed = package().rsplit(f"TARGET_HEAD_SHA: {HEAD}", 1)[0]
        with self.assertRaises(TransportVerificationError):
            parse_identity(malformed)


if __name__ == "__main__":
    unittest.main()
