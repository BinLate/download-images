import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from verify_review_target import TargetVerificationError, verify_target  # noqa: E402

REVIEW_URL = "https://chatgpt.com/"
OTHER_CONVERSATION = "https://chatgpt.com/c/6a853b00-6988-83ec-9b19-5f8c43c257ca"


def snapshot(**overrides):
    data = {
        "page_url": REVIEW_URL,
        "document_has_focus": True,
        "composer_found": True,
        "composer_visible": True,
        "composer_enabled": True,
        "active_is_composer": True,
        "composer_selector": "#prompt-textarea",
        "composer_tag": "textarea",
        "composer_role": "textbox",
        "composer_contenteditable": False,
    }
    data.update(overrides)
    return data


class ReviewTargetTests(unittest.TestCase):
    def test_exact_focused_composer_passes(self):
        result = verify_target(snapshot(), REVIEW_URL)
        self.assertTrue(result["ok"])
        self.assertTrue(result["active_is_composer"])

    def test_address_bar_focus_fails_closed(self):
        with self.assertRaisesRegex(TargetVerificationError, "address bar"):
            verify_target(snapshot(document_has_focus=False, active_is_composer=False), REVIEW_URL)

    def test_page_body_or_other_element_focus_fails_closed(self):
        with self.assertRaisesRegex(TargetVerificationError, "not document.activeElement"):
            verify_target(snapshot(active_is_composer=False), REVIEW_URL)

    def test_clipboard_url_navigation_to_other_chat_fails(self):
        with self.assertRaisesRegex(TargetVerificationError, "URL changed"):
            verify_target(snapshot(page_url=OTHER_CONVERSATION), REVIEW_URL)

    def test_non_chatgpt_host_fails(self):
        with self.assertRaisesRegex(TargetVerificationError, "unexpected review host"):
            verify_target(snapshot(page_url="https://example.com/"), REVIEW_URL)

    def test_hidden_composer_fails(self):
        with self.assertRaisesRegex(TargetVerificationError, "not visible"):
            verify_target(snapshot(composer_visible=False), REVIEW_URL)

    def test_disabled_composer_fails(self):
        with self.assertRaisesRegex(TargetVerificationError, "not enabled"):
            verify_target(snapshot(composer_enabled=False), REVIEW_URL)

    def test_unknown_selector_fails(self):
        with self.assertRaisesRegex(TargetVerificationError, "unrecognized composer selector"):
            verify_target(snapshot(composer_selector="#search-box"), REVIEW_URL)


if __name__ == "__main__":
    unittest.main()
