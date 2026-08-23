#!/usr/bin/env python3
"""Deterministic Browser Candidate Discovery & Ranking for independent ChatGPT review."""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class BrowserOwner(str, Enum):
    ANTIGRAVITY_MANAGED = "ANTIGRAVITY_MANAGED"
    FALLBACK_REVIEWER_CHROME = "FALLBACK_REVIEWER_CHROME"
    EXISTING_EXTERNAL_CHROME = "EXISTING_EXTERNAL_CHROME"
    UNKNOWN = "UNKNOWN"


@dataclass
class BrowserCandidate:
    endpoint: str
    port: int
    pid: int | None = None
    parent_pid: int | None = None
    executable: str = ""
    command_line: str = ""
    user_data_dir: str = ""
    owner: BrowserOwner = BrowserOwner.UNKNOWN
    targets: list[dict[str, Any]] = field(default_factory=list)
    score: int = 0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["owner"] = self.owner.value
        return d


def find_free_port() -> int:
    """Find a guaranteed free TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def query_devtools_endpoint(port: int, timeout_sec: float = 1.2) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """Query /json/version and /json/list on a potential DevTools port."""
    version_data: dict[str, Any] | None = None
    targets_data: list[dict[str, Any]] = []

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/json/version",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            version_data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None, []

    if not version_data or not isinstance(version_data, dict):
        return None, []

    try:
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/json/list",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw_list = json.loads(resp.read().decode("utf-8"))
            if isinstance(raw_list, list):
                targets_data = raw_list
    except Exception:
        targets_data = []

    return version_data, targets_data


def _get_windows_processes() -> list[dict[str, Any]]:
    """Query Win32_Process via PowerShell to inspect running browser processes."""
    ps_script = """
    Get-CimInstance Win32_Process | Where-Object {
        $_.Name -match 'chrome|msedge|electron|antigravity|node' -or
        $_.CommandLine -match 'remote-debugging-port'
    } | Select-Object ProcessId, ParentProcessId, Name, ExecutablePath, CommandLine | ConvertTo-Json -Compress
    """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=8,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        data = json.loads(proc.stdout)
        if isinstance(data, dict):
            return [data]
        if isinstance(data, list):
            return data
    except Exception:
        pass
    return []


def _get_listening_ports() -> dict[int, int]:
    """Map listening local TCP ports to their owning PIDs via netstat."""
    port_to_pid: dict[int, int] = {}
    try:
        proc = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        for line in proc.stdout.splitlines():
            line = line.strip()
            if "LISTENING" in line and "127.0.0.1:" in line:
                parts = line.split()
                if len(parts) >= 5:
                    addr_part = parts[1]
                    pid_str = parts[4]
                    if ":" in addr_part and pid_str.isdigit():
                        port = int(addr_part.split(":")[-1])
                        port_to_pid[port] = int(pid_str)
    except Exception:
        pass
    return port_to_pid


def classify_candidate(
    candidate: BrowserCandidate,
    procs_by_pid: dict[int, dict[str, Any]],
    version_info: dict[str, Any] | None,
    targets: list[dict[str, Any]],
) -> None:
    """Classify and score a candidate endpoint deterministically."""
    browser_str = str(version_info.get("Browser", "") if version_info else "")
    cmdline = candidate.command_line.lower()
    proc_name = (candidate.executable or "").lower()

    # If it's pure node.js without page targets -> UNKNOWN, reject
    if "node.js" in browser_str.lower() and not any(t.get("type") == "page" for t in targets):
        candidate.owner = BrowserOwner.UNKNOWN
        candidate.score = -100
        candidate.reason = "Node.js debugger target with no web page targets"
        return

    # Check if PID or parent PID belongs to Antigravity IDE / agy
    is_antigravity_ancestor = False
    cur_ppid = candidate.parent_pid
    visited_pids = set()
    while cur_ppid and cur_ppid not in visited_pids:
        visited_pids.add(cur_ppid)
        parent_proc = procs_by_pid.get(cur_ppid)
        if not parent_proc:
            break
        pname = str(parent_proc.get("Name", "")).lower()
        pcmd = str(parent_proc.get("CommandLine", "")).lower()
        if "antigravity" in pname or "antigravity" in pcmd or "electron" in pname:
            is_antigravity_ancestor = True
            break
        cur_ppid = parent_proc.get("ParentProcessId")

    # Check user data dir markers
    is_reviewer_profile = (
        "chrome-reviewer-profile" in cmdline
        or "geminichatgptreviewer" in cmdline
        or "chrome-reviewer-profile" in candidate.user_data_dir.lower()
    )

    page_targets = [t for t in targets if t.get("type") == "page"]
    has_chatgpt_tab = any("chatgpt.com" in str(t.get("url", "")).lower() for t in page_targets)

    if is_antigravity_ancestor or "antigravity" in cmdline:
        candidate.owner = BrowserOwner.ANTIGRAVITY_MANAGED
        candidate.score = 100 + (20 if has_chatgpt_tab else 0) + len(page_targets)
        candidate.reason = "Antigravity IDE managed process hierarchy"
        if has_chatgpt_tab:
            candidate.reason += " with existing ChatGPT tab"
    elif is_reviewer_profile:
        candidate.owner = BrowserOwner.FALLBACK_REVIEWER_CHROME
        candidate.score = 50 + (10 if has_chatgpt_tab else 0) + len(page_targets)
        candidate.reason = "Dedicated persistent reviewer Chrome profile instance"
    elif page_targets:
        candidate.owner = BrowserOwner.EXISTING_EXTERNAL_CHROME
        candidate.score = -10
        candidate.reason = "External unmanaged Chrome instance; not selected by default"
    else:
        candidate.owner = BrowserOwner.UNKNOWN
        candidate.score = -50
        candidate.reason = "Unusable DevTools target without page targets"


def discover_candidates(ports_to_probe: list[int] | None = None) -> list[BrowserCandidate]:
    """Discover all reachable DevTools endpoints, classify and rank them."""
    procs = _get_windows_processes()
    procs_by_pid: dict[int, dict[str, Any]] = {
        p["ProcessId"]: p for p in procs if p.get("ProcessId")
    }

    port_to_pid = _get_listening_ports()
    detected_ports: set[int] = set(ports_to_probe or [])

    # Extract remote debugging ports from command lines
    for p in procs:
        cmd = str(p.get("CommandLine") or "")
        m = re.search(r"--remote-debugging-port=(\d+)", cmd)
        if m:
            detected_ports.add(int(m.group(1)))

    # Also check known common debugging ports if listening
    for p in port_to_pid:
        if 9222 <= p <= 9250 or 9333 <= p <= 9360:
            detected_ports.add(p)

    candidates: list[BrowserCandidate] = []

    for port in sorted(detected_ports):
        version_info, targets = query_devtools_endpoint(port)
        if not version_info:
            continue

        pid = port_to_pid.get(port)
        proc_info = procs_by_pid.get(pid) if pid else None

        cmdline = ""
        executable = ""
        parent_pid = None
        user_data_dir = ""

        if proc_info:
            cmdline = str(proc_info.get("CommandLine") or "")
            executable = str(proc_info.get("ExecutablePath") or proc_info.get("Name") or "")
            parent_pid = proc_info.get("ParentProcessId")
            m_udd = re.search(r'--user-data-dir=(?:"([^"]+)"|([^\s]+))', cmdline)
            if m_udd:
                user_data_dir = m_udd.group(1) or m_udd.group(2) or ""

        cand = BrowserCandidate(
            endpoint=f"http://127.0.0.1:{port}",
            port=port,
            pid=pid,
            parent_pid=parent_pid,
            executable=executable,
            command_line=cmdline,
            user_data_dir=user_data_dir,
            targets=targets,
        )
        classify_candidate(cand, procs_by_pid, version_info, targets)
        candidates.append(cand)

    # Sort descending by score, then ascending by port
    candidates.sort(key=lambda c: (-c.score, c.port))
    return candidates


def select_best_browser(candidates: list[BrowserCandidate]) -> BrowserCandidate | None:
    """Select the best usable browser candidate, or None if fallback launch is needed."""
    usable = [
        c for c in candidates
        if c.owner in (BrowserOwner.ANTIGRAVITY_MANAGED, BrowserOwner.FALLBACK_REVIEWER_CHROME)
        and c.score > 0
    ]
    return usable[0] if usable else None
