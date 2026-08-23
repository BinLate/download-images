#!/usr/bin/env python3
"""V1 workflow-state compatibility facade.

Without an active v2 task this preserves the original review-state.json behavior.
When .ai/active-task.json exists next to the legacy file, show/set/next-round are
projected/delegated to the authoritative v2 task state instead of creating a
second source of truth.
"""
import argparse
import json
from pathlib import Path
from datetime import datetime, timezone

VALID_STATES = {
    'TASK_RECEIVED','PLANNING','IMPLEMENTING','VERIFYING','CREATE_OR_UPDATE_PR',
    'REVIEWING','FIXING','RELEASE_GATE','APPROVED','HUMAN_DECISION','FAILED'
}
V1_TO_V2 = {
    'TASK_RECEIVED': 'RECEIVED',
    'PLANNING': 'PLANNING',
    'IMPLEMENTING': 'IMPLEMENTING',
    'VERIFYING': 'VERIFYING',
    'CREATE_OR_UPDATE_PR': 'PR_PREPARING',
    'REVIEWING': 'REVIEWING',
    'FIXING': 'FIXING',
    'RELEASE_GATE': 'RELEASE_GATE',
    'APPROVED': 'APPROVED',
    'HUMAN_DECISION': 'HUMAN_DECISION',
    'FAILED': 'FAILED',
}
V2_TO_V1 = {v: k for k, v in V1_TO_V2.items()}


def load(path):
    p = Path(path)
    if not p.exists():
        raise SystemExit(f'State file not found: {p}')
    return json.loads(p.read_text(encoding='utf-8'))


def save(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data['updated_at'] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def _project_root(file_path):
    p = Path(file_path).resolve()
    return p.parent.parent if p.parent.name == '.ai' else None


def _v2_available(file_path):
    root = _project_root(file_path)
    return root is not None and (root / '.ai' / 'active-task.json').exists()


def _load_v2(file_path):
    root = _project_root(file_path)
    if root is None:
        raise SystemExit('Cannot resolve project root for v2 compatibility')
    from task_store import TaskStoreError, load_task
    try:
        return root, load_task(root)
    except TaskStoreError as exc:
        raise SystemExit(f'v2 state error: {exc}') from exc


def _v1_projection(state):
    lifecycle = state['lifecycle']['current_state']
    return {
        'task_id': state['identity']['id'],
        'state': V2_TO_V1.get(lifecycle, lifecycle),
        'review_round': state['review']['round'],
        'max_review_rounds': state['review']['max_rounds'],
        'review': state['review']['current_verdict'],
        'ci': state['verification']['overall_status'],
        'pr_number': state['delivery']['pr_number'],
        'pr_url': state['delivery']['pr_url'],
        'base_sha': None,
        'head_sha': state['delivery']['head_sha'],
        'v2_authoritative': True,
    }


def _set_v2(file_path, state_name, review=None, ci=None):
    root, state = _load_v2(file_path)
    from task_store import TaskStoreError, save_task, transition_task
    target = V1_TO_V2[state_name]
    try:
        if review is not None or ci is not None:
            updated = json.loads(json.dumps(state))
            if review is not None:
                updated['review']['current_verdict'] = review
                updated['review']['approval_valid'] = review == 'APPROVED_TO_MERGE'
            if ci is not None:
                updated['verification']['overall_status'] = ci
            save_task(root, updated)
            state = updated
        if state['lifecycle']['current_state'] != target:
            state = transition_task(root, target, f'v1 compatibility requested {state_name}', task_id=state['identity']['id'])
        return _v1_projection(state)
    except TaskStoreError as exc:
        raise SystemExit(f'v2 state error: {exc}') from exc


def _next_round_v2(file_path):
    root, state = _load_v2(file_path)
    from orchestrator import OrchestratorError, enter_review
    try:
        if state['lifecycle']['current_state'] != 'PR_PREPARING':
            raise SystemExit('v2 next-round requires PR_PREPARING after a newly verified/pushed HEAD')
        state = enter_review(root, task_id=state['identity']['id'])
        return _v1_projection(state)
    except OrchestratorError as exc:
        raise SystemExit(f'v2 state error: {exc}') from exc


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('init')
    p.add_argument('--task', required=True)
    p.add_argument('--max-rounds', type=int, default=5)
    p.add_argument('--file', required=True)
    p = sp.add_parser('show')
    p.add_argument('--file', required=True)
    p = sp.add_parser('set')
    p.add_argument('--file', required=True)
    p.add_argument('--state', choices=sorted(VALID_STATES), required=True)
    p.add_argument('--review')
    p.add_argument('--ci')
    p = sp.add_parser('next-round')
    p.add_argument('--file', required=True)
    args = ap.parse_args()

    # init intentionally remains v1-compatible. New v2 tasks are created by
    # orchestrator.py; this prevents legacy callers from unexpectedly creating
    # authoritative task state.
    if args.cmd != 'init' and _v2_available(args.file):
        if args.cmd == 'show':
            _, state = _load_v2(args.file)
            print(json.dumps(_v1_projection(state), indent=2, sort_keys=True))
            return
        if args.cmd == 'set':
            print(json.dumps(_set_v2(args.file, args.state, args.review, args.ci), indent=2, sort_keys=True))
            return
        if args.cmd == 'next-round':
            print(json.dumps(_next_round_v2(args.file), indent=2, sort_keys=True))
            return

    if args.cmd == 'init':
        if args.max_rounds < 1 or args.max_rounds > 20:
            raise SystemExit('max-rounds must be between 1 and 20')
        d = {'task_id': args.task, 'state': 'TASK_RECEIVED', 'review_round': 0,
             'max_review_rounds': args.max_rounds, 'review': None, 'ci': None,
             'pr_number': None, 'pr_url': None, 'base_sha': None, 'head_sha': None}
        save(args.file, d)
        print(json.dumps(d, indent=2))
    elif args.cmd == 'show':
        print(json.dumps(load(args.file), indent=2, sort_keys=True))
    elif args.cmd == 'set':
        d = load(args.file)
        d['state'] = args.state
        if args.review is not None: d['review'] = args.review
        if args.ci is not None: d['ci'] = args.ci
        save(args.file, d)
        print(json.dumps(d, indent=2, sort_keys=True))
    elif args.cmd == 'next-round':
        d = load(args.file)
        current = int(d.get('review_round', 0))
        maximum = int(d.get('max_review_rounds', 5))
        if current >= maximum:
            raise SystemExit(f'Review round limit reached ({current}/{maximum})')
        d['review_round'] = current + 1
        d['state'] = 'REVIEWING'
        save(args.file, d)
        print(json.dumps(d, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
