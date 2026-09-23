# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The audit log — who did what, when, to which evidence. Append-only and hash-chained.

Every ``evidence`` command that produces or approves something appends one line:

    {"seq": 12, "at": "...", "actor": "jdoe", "action": "approve",
     "subject": "changes/...", "details": {...}, "prev": "<hash of line 11>", "hash": "..."}

Each line carries the hash of the line before it, so deleting, reordering or
editing any line breaks the chain from that point on, and ``evidence audit``
names where.

Who the actor is: ``EVIDENCE_ACTOR`` if set, else the operating-system user.
That is accountability, not authentication — inside a bank this is wired to its
single sign-on, which is the bank's identity system to provide.

Roles (``settings/roles.yaml``) say who may approve a change. The same caveat
applies: a role check against an unauthenticated name deters mistakes, not
attackers.
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

import yaml

from evidence.runner import now

LOG_ENV = "EVIDENCE_AUDIT_LOG"
DEFAULT_LOG = "audit/audit_log.jsonl"
GENESIS = "0" * 64


def log_path() -> Path:
    return Path(os.environ.get(LOG_ENV, DEFAULT_LOG))


def actor() -> str:
    return os.environ.get("EVIDENCE_ACTOR") or getpass.getuser()


def _hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
                          ).hexdigest()


def _lines(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def record(action: str, subject: str, details: dict[str, Any] | None = None,
           path: Path | None = None) -> dict:
    path = path or log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    prior = _lines(path)
    entry = {
        "seq": len(prior) + 1,
        "at": now(),
        "actor": actor(),
        "action": action,
        "subject": subject,
        "details": details or {},
        "prev": prior[-1]["hash"] if prior else GENESIS,
    }
    entry["hash"] = _hash(entry)
    with path.open("a") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def verify_log(path: Path | None = None) -> list[str]:
    """Problems with the chain, first break first. Empty means intact."""
    path = path or log_path()
    problems = []
    prev = GENESIS
    for i, e in enumerate(_lines(path), 1):
        if e.get("seq") != i:
            problems.append(f"line {i}: sequence {e.get('seq')} — a line was removed or moved")
        if e.get("prev") != prev:
            problems.append(f"line {i}: does not follow line {i - 1} — the chain is broken here")
        if _hash(e) != e.get("hash"):
            problems.append(f"line {i}: content changed after it was written")
        prev = e.get("hash")
    return problems


def roles(path: str | Path = "settings/roles.yaml") -> dict[str, list[str]]:
    p = Path(path)
    if not p.exists():
        return {}
    return {u: list(r) for u, r in (yaml.safe_load(p.read_text()) or {}).get("users", {}).items()}


def require_role(role: str, path: str | Path = "settings/roles.yaml") -> str:
    who = actor()
    table = roles(path)
    if role not in table.get(who, []):
        raise PermissionError(
            f"{who!r} does not hold the {role!r} role in {path}. Ask whoever maintains the roles "
            f"file, or set EVIDENCE_ACTOR if you are acting for someone who does.")
    return who
