import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from state_machine import StateTransitionError, transition_state, validate_transition
from task_store import new_task_state

NOW = '2026-08-19T07:00:00+00:00'
SHA = '0123456789abcdef0123456789abcdef01234567'
OTHER = 'fedcba9876543210fedcba9876543210fedcba98'
TASK_ID = 'T-20260819-001-state-machine'


def base_state():
    return new_task_state(TASK_ID, 'Implement state machine', 'state machine', timestamp=NOW)


class StateMachineTests(unittest.TestCase):
    def classified(self, tier='SIMPLE', risk='LOW'):
        state = base_state()
        state['classification'].update({'complexity_tier': tier, 'risk_level': risk, 'kind': 'MAINTENANCE'})
        return transition_state(state, 'CLASSIFIED', 'classification complete', now=NOW)[0]

    def test_received_requires_resolved_classification_before_classified(self):
        with self.assertRaises(StateTransitionError):
            transition_state(base_state(), 'CLASSIFIED', 'not classified', now=NOW)

    def test_simple_routes_directly_to_implementing(self):
        state = self.classified('SIMPLE')
        result, history = transition_state(state, 'IMPLEMENTING', 'simple route', now=NOW)
        self.assertEqual(result['lifecycle']['current_state'], 'IMPLEMENTING')
        self.assertEqual(history['from'], 'CLASSIFIED')

    def test_standard_cannot_skip_planning(self):
        state = self.classified('STANDARD')
        with self.assertRaises(StateTransitionError):
            transition_state(state, 'IMPLEMENTING', 'skip plan', now=NOW)

    def test_implementing_cannot_jump_to_reviewing(self):
        state = self.classified('SIMPLE')
        state = transition_state(state, 'IMPLEMENTING', 'start', now=NOW)[0]
        with self.assertRaises(StateTransitionError):
            transition_state(state, 'REVIEWING', 'illegal jump', now=NOW)

    def test_blocked_resumes_only_to_recorded_state(self):
        state = self.classified('SIMPLE')
        state = transition_state(state, 'IMPLEMENTING', 'start', now=NOW)[0]
        blocked = transition_state(state, 'BLOCKED', 'dependency missing', now=NOW)[0]
        self.assertEqual(blocked['lifecycle']['resume_state'], 'IMPLEMENTING')
        with self.assertRaises(StateTransitionError):
            transition_state(blocked, 'VERIFYING', 'wrong resume', now=NOW)
        resumed = transition_state(blocked, 'IMPLEMENTING', 'dependency restored', now=NOW)[0]
        self.assertIsNone(resumed['lifecycle']['resume_state'])

    def test_human_decision_requires_explicit_authorization(self):
        state = self.classified('SIMPLE')
        human = transition_state(state, 'HUMAN_DECISION', 'manual choice', now=NOW)[0]
        with self.assertRaises(StateTransitionError):
            transition_state(human, 'IMPLEMENTING', 'continue', now=NOW)
        resumed = transition_state(human, 'IMPLEMENTING', 'human approved', human_authorized=True, actor='HUMAN', now=NOW)[0]
        self.assertEqual(resumed['lifecycle']['current_state'], 'IMPLEMENTING')

    def test_review_entry_requires_open_pr_and_full_sha_and_increments_round(self):
        state = self.classified('SIMPLE')
        state['lifecycle']['current_state'] = 'PR_PREPARING'
        with self.assertRaises(StateTransitionError):
            transition_state(state, 'REVIEWING', 'review', now=NOW)
        state['delivery'].update({'pr_number': 1, 'pr_url': 'https://github.com/o/r/pull/1', 'pr_state': 'OPEN', 'head_sha': SHA})
        reviewed = transition_state(state, 'REVIEWING', 'review round', now=NOW)[0]
        self.assertEqual(reviewed['review']['round'], 1)
        self.assertEqual(reviewed['review']['current_target_sha'], SHA)

    def test_release_gate_requires_exact_valid_approval(self):
        state = self.classified('SIMPLE')
        state['lifecycle']['current_state'] = 'REVIEWING'
        state['review'].update({'round': 1, 'current_verdict': 'APPROVED_TO_MERGE', 'current_target_sha': OTHER, 'approval_valid': True})
        state['delivery'].update({'pr_number': 1, 'pr_url': 'https://github.com/o/r/pull/1', 'pr_state': 'OPEN', 'head_sha': SHA})
        with self.assertRaises(StateTransitionError):
            transition_state(state, 'RELEASE_GATE', 'approval', now=NOW)
        state['review']['current_target_sha'] = SHA
        gated = transition_state(state, 'RELEASE_GATE', 'approval', now=NOW)[0]
        self.assertEqual(gated['release']['approved_sha'], SHA)

    def test_review_limit_requires_max_round(self):
        state = self.classified('SIMPLE')
        state['lifecycle']['current_state'] = 'REVIEWING'
        state['review']['round'] = 4
        with self.assertRaises(StateTransitionError):
            transition_state(state, 'REVIEW_LIMIT_REACHED', 'too early', now=NOW)
        state['review']['round'] = 5
        limited = transition_state(state, 'REVIEW_LIMIT_REACHED', 'limit hit', now=NOW)[0]
        self.assertEqual(limited['lifecycle']['current_state'], 'REVIEW_LIMIT_REACHED')


if __name__ == '__main__':
    unittest.main()
