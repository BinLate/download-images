#!/usr/bin/env python3
import argparse
import json
import re
import subprocess
from pathlib import Path
from datetime import datetime, timezone

FULL_SHA_RE = re.compile(r'^[0-9a-fA-F]{40}$')

import shutil
import os

def run(cmd):
    binary = shutil.which(cmd[0]) or cmd[0]
    p = subprocess.run([binary] + list(cmd[1:]), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=(os.name == 'nt'))
    if p.returncode != 0:
        raise SystemExit(f"Command failed: {' '.join(cmd)}\n{p.stderr.strip()}")
    return p.stdout.strip()

def full_sha(value, label):
    value = str(value or '').lower()
    if not FULL_SHA_RE.fullmatch(value):
        raise SystemExit(f'{label} must be exactly 40 hexadecimal characters.')
    return value

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--write', required=True)
    args = ap.parse_args()

    repo_j = json.loads(run(['gh','repo','view','--json','nameWithOwner,url']))
    pr_j = json.loads(run(['gh','pr','view','--json','number,url,headRefName,headRefOid,baseRefName,baseRefOid,state']))
    if str(pr_j.get('state', '')).upper() != 'OPEN':
        raise SystemExit(f"PR must be OPEN before review; current state is {pr_j.get('state')!r}.")
    git_head = full_sha(run(['git','rev-parse','HEAD']), 'Local HEAD')
    pr_head = full_sha(pr_j.get('headRefOid'), 'PR HEAD')
    base_sha = full_sha(pr_j.get('baseRefOid'), 'PR base SHA')
    if git_head != pr_head:
        raise SystemExit(f'Local HEAD ({git_head}) does not match PR HEAD ({pr_head}). Push/reconcile before review.')

    path = Path(args.write)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as exc:
            raise SystemExit(f'Existing review state is corrupt: {exc}')
    else:
        data = {'review_round': 0, 'max_review_rounds': 5}
    old_head = str(data.get('head_sha') or '').lower()
    if old_head and old_head != pr_head:
        data['approval_valid'] = False
        data['current_verdict'] = None
        data['approved_sha'] = None
    data.update({
        'repository': repo_j['nameWithOwner'], 'repository_url': repo_j['url'],
        'pr_number': pr_j['number'], 'pr_url': pr_j['url'], 'pr_state': 'OPEN',
        'head_branch': pr_j['headRefName'], 'base_branch': pr_j['baseRefName'],
        'head_sha': pr_head, 'base_sha': base_sha, 'current_target_sha': pr_head,
        'updated_at': datetime.now(timezone.utc).isoformat()
    })
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps(data, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
