# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Verifying an evidence pack — re-read every file, recompute every number.

    report = verify("evidence/baseline-proof")
    print(report.render())

In order:

1. **Files.** Every file matches its checksum; nothing is missing, nothing was
   added; the root hash matches. If a sealing key is available, the seal matches.
2. **Inputs agree with each other.** The case pack matches the hash the run
   recorded; the settings match the hash every transcript recorded; every
   transcript matches its own content hash.
3. **Every derived file is recomputed** from the inputs and compared. For JSON,
   the first differing value is named by its path — "aggregate.json:
   checks.material_omission.pass_rate stored 0.52, recomputed 0.43".

Step 3 is why the checksums alone are not the guarantee: someone who edits a
number and regenerates CHECKSUMS.json still fails, because the number no longer
follows from the transcripts.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evidence.derive import INPUT_FILES, derive, load_inputs
from evidence.evidence_pack.writer import CHECKSUMS, SEAL_ENV, root_hash, seal, sha256_file
from evidence.settings import Settings
from evidence.signing import SIG_NAME, verify_signature


@dataclass
class VerifyReport:
    root: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def render(self) -> str:
        lines = [f"Evidence pack: {self.root}"]
        lines += [f"  ok    {c}" for c in self.checked]
        lines += [f"  WARN  {w}" for w in self.warnings]
        lines += [f"  FAIL  {e}" for e in self.errors]
        lines.append("VERIFIED" if self.ok else f"REJECTED — {len(self.errors)} problem(s)")
        return "\n".join(lines)


def _first_difference(a: Any, b: Any, path: str = "") -> tuple[str, Any, Any] | None:
    if type(a) is not type(b):
        return path or "(root)", a, b
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                return f"{path}.{k}".lstrip("."), a.get(k, "<missing>"), b.get(k, "<missing>")
            d = _first_difference(a[k], b[k], f"{path}.{k}")
            if d:
                return d
        return None
    if isinstance(a, list):
        if len(a) != len(b):
            return f"{path} (length)".lstrip("."), len(a), len(b)
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            d = _first_difference(x, y, f"{path}[{i}]")
            if d:
                return d
        return None
    return None if a == b else (path.lstrip("."), a, b)


def _compare(rel: str, stored: bytes, fresh: bytes) -> str | None:
    if stored == fresh:
        return None
    if rel.endswith(".json"):
        d = _first_difference(json.loads(stored), json.loads(fresh))
        if d:
            return f"{rel}: {d[0]} — stored {d[1]!r}, recomputed {d[2]!r}"
    if rel.endswith(".jsonl"):
        s_lines, f_lines = stored.decode().splitlines(), fresh.decode().splitlines()
        for i, (s, f) in enumerate(zip(s_lines, f_lines, strict=False)):
            if s != f:
                d = _first_difference(json.loads(s), json.loads(f))
                where = json.loads(f).get("result_id", f"line {i + 1}")
                if d:
                    return f"{rel}: {where} {d[0]} — stored {d[1]!r}, recomputed {d[2]!r}"
        return f"{rel}: {len(s_lines)} lines stored, {len(f_lines)} recomputed"
    return f"{rel}: content does not match what the transcripts produce"


def verify(root: str | Path, *, seal_key: str | None = None,
           allowed_signers: str | Path | None = None) -> VerifyReport:
    root = Path(root)
    rep = VerifyReport(root=root)
    ck_path = root / CHECKSUMS
    if not ck_path.exists():
        rep.errors.append(f"{CHECKSUMS} missing")
        return rep
    ck = json.loads(ck_path.read_text())
    listed: dict[str, str] = ck.get("files", {})

    # 1. files
    present = {str(p.relative_to(root)) for p in root.rglob("*")
               if p.is_file() and p.name not in (CHECKSUMS, SIG_NAME)}
    for rel in sorted(set(listed) - present):
        rep.errors.append(f"{rel}: listed in {CHECKSUMS} but missing")
    for rel in sorted(present - set(listed)):
        rep.errors.append(f"{rel}: present but not listed in {CHECKSUMS}")
    changed = [rel for rel in sorted(set(listed) & present)
               if sha256_file(root / rel) != listed[rel]]
    for rel in changed:
        rep.errors.append(f"{rel}: changed since the pack was written (checksum mismatch)")
    if root_hash(listed) != ck.get("root"):
        rep.errors.append(f"{CHECKSUMS}: root hash does not match its file list")
    if not changed and not rep.errors:
        rep.checked.append(f"{len(listed)} files match their checksums")

    key = seal_key or os.environ.get(SEAL_ENV)
    s = ck.get("seal")
    if s and key:
        if seal(ck["root"], key) == s.get("value"):
            rep.checked.append("seal matches (HMAC-SHA256)")
        else:
            rep.errors.append("seal does not match — altered, or sealed with a different key")
    elif s:
        rep.warnings.append(f"sealed, but no key available to check it (set {SEAL_ENV})")
    else:
        rep.warnings.append("not sealed")

    if allowed_signers:
        ok, msg = verify_signature(root, allowed_signers)
        (rep.checked if ok else rep.errors).append(f"signature: {msg}")
    elif (root / SIG_NAME).exists():
        rep.warnings.append("signed, but no allowed-signers file given to check it against")

    missing_inputs = [f for f in INPUT_FILES if not (root / f).exists()]
    if missing_inputs:
        rep.errors.append(f"inputs missing, cannot recompute: {missing_inputs}")
        return rep

    # 2. inputs agree with each other
    inp = load_inputs(root)
    items_sha = hashlib.sha256((root / "items.jsonl").read_bytes()).hexdigest()
    if inp.run["pack_items_sha256"] != items_sha:
        rep.errors.append("items.jsonl is not the case pack this run used")
    settings_sha = Settings.model_validate(yaml.safe_load((root / "settings.yaml").read_text())
                                           ).sha256()
    if inp.run["settings_sha256"] != settings_sha:
        rep.errors.append("settings.yaml is not the settings this run used")
    bad_t = [t.item_id for t in inp.transcripts if not t.verify_hash()]
    wrong_settings = [t.item_id for t in inp.transcripts
                      if t.sut.settings_sha256 not in (None, inp.run["settings_sha256"])]
    if bad_t:
        rep.errors.append(f"transcripts.jsonl: {len(bad_t)} transcript(s) altered, e.g. {bad_t[0]}")
    if wrong_settings:
        rep.errors.append(f"transcripts.jsonl: {len(wrong_settings)} transcript(s) from other "
                          f"settings, e.g. {wrong_settings[0]}")
    if not (bad_t or wrong_settings):
        rep.checked.append(f"{len(inp.transcripts)} transcripts match their content hashes")

    # 3. recompute every derived file
    fresh = derive(inp)
    mismatches = 0
    for rel, body in sorted(fresh.items()):
        path = root / rel
        if not path.exists():
            rep.errors.append(f"{rel}: derived file missing")
            mismatches += 1
            continue
        diff = _compare(rel, path.read_bytes(), body)
        if diff:
            rep.errors.append(diff)
            mismatches += 1
    if not mismatches:
        rep.checked.append(f"{len(fresh)} derived files recomputed from the transcripts and match")
    return rep
