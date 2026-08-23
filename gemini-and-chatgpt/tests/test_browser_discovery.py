import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from browser_discovery import (  # noqa: E402
    BrowserCandidate,
    BrowserOwner,
    classify_candidate,
    discover_candidates,
    find_free_port,
    select_best_browser,
)


class BrowserDiscoveryTests(unittest.TestCase):
    def test_find_free_port_allocates_valid_port(self):
        port = find_free_port()
        self.assertIsInstance(port, int)
        self.assertGreater(port, 1024)
        self.assertLessEqual(port, 65535)

    def test_case_a_unrelated_unknown_browser_on_9222_rejected(self):
        """Case A: 9222 is open but is unrelated/unknown browser -> not selected."""
        cand = BrowserCandidate(
            endpoint="http://127.0.0.1:9222",
            port=9222,
            pid=9999,
            parent_pid=1,
            executable="unknown_service.exe",
            command_line="unknown_service.exe --debug",
        )
        procs_by_pid = {9999: {"Name": "unknown_service.exe", "CommandLine": "unknown_service.exe"}}
        version_info = {"Browser": "CustomTool/1.0"}
        targets = []

        classify_candidate(cand, procs_by_pid, version_info, targets)
        self.assertEqual(cand.owner, BrowserOwner.UNKNOWN)
        self.assertLess(cand.score, 0)
        self.assertIsNone(select_best_browser([cand]))

    def test_case_b_antigravity_managed_chrome_on_dynamic_port_selected(self):
        """Case B: Antigravity-managed Chrome on dynamic port -> discovered & selected."""
        cand = BrowserCandidate(
            endpoint="http://127.0.0.1:49152",
            port=49152,
            pid=5555,
            parent_pid=1000,
            executable="chrome.exe",
            command_line="chrome.exe --remote-debugging-port=49152",
        )
        procs_by_pid = {
            5555: {"ProcessId": 5555, "ParentProcessId": 1000, "Name": "chrome.exe", "CommandLine": "chrome.exe --remote-debugging-port=49152"},
            1000: {"ProcessId": 1000, "ParentProcessId": 1, "Name": "Antigravity IDE.exe", "CommandLine": "Antigravity IDE.exe"},
        }
        version_info = {"Browser": "Chrome/130.0"}
        targets = [{"type": "page", "url": "about:blank"}]

        classify_candidate(cand, procs_by_pid, version_info, targets)
        self.assertEqual(cand.owner, BrowserOwner.ANTIGRAVITY_MANAGED)
        self.assertGreater(cand.score, 90)
        best = select_best_browser([cand])
        self.assertIsNotNone(best)
        self.assertEqual(best.port, 49152)

    def test_case_c_antigravity_chrome_beats_unrelated_chrome(self):
        """Case C: Both unrelated Chrome and Antigravity Chrome exist -> Antigravity wins."""
        unrelated = BrowserCandidate(
            endpoint="http://127.0.0.1:9222",
            port=9222,
            pid=2000,
            parent_pid=1,
            executable="chrome.exe",
            command_line="chrome.exe --remote-debugging-port=9222",
        )
        ag_cand = BrowserCandidate(
            endpoint="http://127.0.0.1:45000",
            port=45000,
            pid=3000,
            parent_pid=1000,
            executable="chrome.exe",
            command_line="chrome.exe --remote-debugging-port=45000",
        )
        procs_by_pid = {
            2000: {"ProcessId": 2000, "ParentProcessId": 1, "Name": "chrome.exe", "CommandLine": "chrome.exe --remote-debugging-port=9222"},
            3000: {"ProcessId": 3000, "ParentProcessId": 1000, "Name": "chrome.exe", "CommandLine": "chrome.exe --remote-debugging-port=45000"},
            1000: {"ProcessId": 1000, "ParentProcessId": 1, "Name": "Antigravity IDE.exe", "CommandLine": "Antigravity IDE.exe"},
        }
        version_info = {"Browser": "Chrome/130.0"}
        targets = [{"type": "page", "url": "https://example.com"}]

        classify_candidate(unrelated, procs_by_pid, version_info, targets)
        classify_candidate(ag_cand, procs_by_pid, version_info, targets)

        cands = [unrelated, ag_cand]
        cands.sort(key=lambda c: (-c.score, c.port))
        best = select_best_browser(cands)
        self.assertIsNotNone(best)
        self.assertEqual(best.owner, BrowserOwner.ANTIGRAVITY_MANAGED)
        self.assertEqual(best.port, 45000)

    def test_case_d_fallback_reviewer_chrome_reused_when_no_antigravity(self):
        """Case D: No Antigravity Chrome, persistent fallback reviewer Chrome is reused."""
        fallback_cand = BrowserCandidate(
            endpoint="http://127.0.0.1:9334",
            port=9334,
            pid=4000,
            parent_pid=1,
            executable="chrome.exe",
            command_line='chrome.exe --remote-debugging-port=9334 --user-data-dir="C:\\Users\\User\\.ai\\chrome-reviewer-profile"',
        )
        procs_by_pid = {
            4000: {"ProcessId": 4000, "ParentProcessId": 1, "Name": "chrome.exe", "CommandLine": fallback_cand.command_line},
        }
        version_info = {"Browser": "Chrome/130.0"}
        targets = [{"type": "page", "url": "https://chatgpt.com/"}]

        classify_candidate(fallback_cand, procs_by_pid, version_info, targets)
        self.assertEqual(fallback_cand.owner, BrowserOwner.FALLBACK_REVIEWER_CHROME)
        self.assertGreater(fallback_cand.score, 40)
        best = select_best_browser([fallback_cand])
        self.assertIsNotNone(best)
        self.assertEqual(best.port, 9334)

    def test_case_e_no_usable_browser_returns_none(self):
        """Case E: No browser exists -> returns None for selection."""
        best = select_best_browser([])
        self.assertIsNone(best)

    def test_case_f_authenticated_chatgpt_tab_boosts_candidate_score(self):
        """Case F: Candidate with chatgpt.com tab gets higher score."""
        cand = BrowserCandidate(
            endpoint="http://127.0.0.1:40000",
            port=40000,
            pid=7000,
            parent_pid=1000,
            executable="chrome.exe",
            command_line="chrome.exe",
        )
        procs_by_pid = {
            7000: {"ProcessId": 7000, "ParentProcessId": 1000, "Name": "chrome.exe", "CommandLine": ""},
            1000: {"ProcessId": 1000, "ParentProcessId": 1, "Name": "Antigravity IDE.exe", "CommandLine": ""},
        }
        version_info = {"Browser": "Chrome/130.0"}
        targets_with_chatgpt = [{"type": "page", "url": "https://chatgpt.com/"}]
        classify_candidate(cand, procs_by_pid, version_info, targets_with_chatgpt)
        self.assertIn("with existing ChatGPT tab", cand.reason)
        self.assertGreaterEqual(cand.score, 120)

    def test_case_g_node_debugger_without_page_targets_classified_unknown(self):
        """Case G: Node.js debugger is classified as UNKNOWN."""
        cand = BrowserCandidate(endpoint="http://127.0.0.1:52355", port=52355)
        procs_by_pid = {}
        version_info = {"Browser": "node.js/v24.18.1"}
        targets = []
        classify_candidate(cand, procs_by_pid, version_info, targets)
        self.assertEqual(cand.owner, BrowserOwner.UNKNOWN)
        self.assertIsNone(select_best_browser([cand]))

    def test_case_h_multiple_devtools_endpoints_ranking_deterministic(self):
        """Case J: Multiple DevTools endpoints sorted deterministically by score and port."""
        c1 = BrowserCandidate(endpoint="http://127.0.0.1:9222", port=9222, score=10)
        c2 = BrowserCandidate(endpoint="http://127.0.0.1:9223", port=9223, score=100)
        c3 = BrowserCandidate(endpoint="http://127.0.0.1:9224", port=9224, score=100)

        cands = [c1, c3, c2]
        cands.sort(key=lambda c: (-c.score, c.port))
        self.assertEqual(cands[0].port, 9223)
        self.assertEqual(cands[1].port, 9224)
        self.assertEqual(cands[2].port, 9222)


if __name__ == "__main__":
    unittest.main()
