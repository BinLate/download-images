import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from verify_review_attachments import AttachmentVerificationError, verify_attachments


def clean_snapshot():
    return {
        "attachment_count": 0,
        "pending_upload_count": 0,
        "has_attachment_preview": False,
        "has_attachment_remove_control": False,
        "has_pending_upload": False,
        "has_upload_error": False,
    }


def test_clean_reviewer_surface_passes():
    assert verify_attachments(clean_snapshot())["ok"] is True


def test_screenshot_attachment_is_rejected_even_when_text_can_be_correct():
    snap = clean_snapshot()
    snap.update({
        "attachment_count": 1,
        "has_attachment_preview": True,
        "has_attachment_remove_control": True,
    })
    with pytest.raises(AttachmentVerificationError, match="non-text attachment"):
        verify_attachments(snap)


def test_pending_clipboard_image_upload_is_rejected():
    snap = clean_snapshot()
    snap.update({"pending_upload_count": 1, "has_pending_upload": True})
    with pytest.raises(AttachmentVerificationError, match="pending"):
        verify_attachments(snap)


def test_missing_attachment_evidence_fails_closed():
    snap = clean_snapshot()
    del snap["attachment_count"]
    with pytest.raises(AttachmentVerificationError, match="attachment_count"):
        verify_attachments(snap)


def test_cli_returns_nonzero_for_image_attachment(tmp_path):
    snap = clean_snapshot()
    snap.update({"attachment_count": 1, "has_attachment_preview": True})
    path = tmp_path / "surface.json"
    out = tmp_path / "result.json"
    path.write_text(json.dumps(snap), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_review_attachments.py"), "--snapshot", str(path), "--json", str(out)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode != 0
    assert json.loads(out.read_text(encoding="utf-8"))["ok"] is False
