# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Stage 5: the audit log, roles and approval, and public-key signatures."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from evidence.audit import record, require_role, verify_log
from evidence.cli import main
from evidence.evidence_pack import verify, write_evidence_pack
from evidence.packs import load_pack
from evidence.runner import run_pack
from evidence.settings import Settings
from evidence.signing import sign, verify_signature

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "underwriter-sample"
pytestmark = pytest.mark.skipif(not (PACK / "items.jsonl").exists(), reason="pack not built")


@pytest.fixture(autouse=True)
def _audit_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("EVIDENCE_AUDIT_LOG", str(tmp_path / "audit.jsonl"))
    monkeypatch.setenv("EVIDENCE_ACTOR", "tester")


# audit log --------------------------------------------------------------------

def test_chain_is_intact_and_breaks_where_edited(tmp_path):
    log = tmp_path / "audit.jsonl"
    for i in range(3):
        record("run", f"evidence/{i}", {"i": i}, path=log)
    assert verify_log(log) == []
    lines = log.read_text().splitlines()
    e = json.loads(lines[1])
    e["subject"] = "evidence/forged"
    lines[1] = json.dumps(e, sort_keys=True)
    log.write_text("\n".join(lines) + "\n")
    problems = verify_log(log)
    assert problems and problems[0].startswith("line 2")


def test_deleted_line_is_detected(tmp_path):
    log = tmp_path / "audit.jsonl"
    for i in range(3):
        record("run", f"x{i}", path=log)
    lines = log.read_text().splitlines()
    log.write_text("\n".join([lines[0], lines[2]]) + "\n")
    assert verify_log(log)


def test_run_command_leaves_an_audit_line(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    rc = main(["run", "--settings", "settings/sim-baseline.yaml", "--split", "proof",
               "--limit", "2", "--repeats", "1", "--runs", str(tmp_path / "r"),
               "--evidence", str(tmp_path / "e")])
    assert rc == 0
    (entry,) = [json.loads(x) for x in (tmp_path / "audit.jsonl").read_text().splitlines()]
    assert entry["action"] == "run" and entry["actor"] == "tester"
    assert entry["details"]["simulated"] is True and entry["details"]["root"]


# roles and approval -----------------------------------------------------------

def omits_reason(system: str, user: str) -> str:
    return "Strong applicant with a long credit history."


def states_reason(system: str, user: str) -> str:
    return "Referred on affordability: debt service exceeds the 40% policy limit."


def _callable_pack(fn: str, tmp: Path) -> Path:
    s = Settings(name=fn, instructions="x",
                 assistant={"adapter": "callable", "callable": f"test_bank:{fn}"},
                 context={"documents": []}, retrieval={"enabled": False}, repeats=1)
    pack = load_pack(PACK)
    run_dir, m = run_pack(pack, s, tmp / "runs", split="proof")
    return write_evidence_pack(run_dir, pack, tmp / "ev" / m.run_id)


@pytest.fixture
def accepted_change(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    monkeypatch.chdir(tmp_path)
    before = _callable_pack("omits_reason", tmp_path)
    after = _callable_pack("states_reason", tmp_path)
    assert main(["diff", str(before), str(after), "--out", str(tmp_path / "chg")]) == 0
    assert json.loads((tmp_path / "chg" / "comparison.json").read_text())["verdict"] == "ACCEPT"
    (tmp_path / "roles.yaml").write_text("users:\n  tester: [approver]\n  bob: [runner]\n")
    return tmp_path


def test_approver_can_approve_an_accepted_change(accepted_change):
    t = accepted_change
    assert main(["approve", str(t / "chg"), "--roles", str(t / "roles.yaml")]) == 0
    log = [json.loads(x) for x in (t / "audit.jsonl").read_text().splitlines()]
    assert [e["action"] for e in log] == ["diff", "approve"]
    assert log[-1]["actor"] == "tester" and verify_log(t / "audit.jsonl") == []


def test_non_approver_is_refused(accepted_change, monkeypatch):
    monkeypatch.setenv("EVIDENCE_ACTOR", "bob")
    with pytest.raises(PermissionError):
        require_role("approver", accepted_change / "roles.yaml")


def test_simulated_change_is_never_approved(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    for s in ("sim-baseline", "sim-with-review-triggers"):
        assert main(["run", "--settings", f"settings/{s}.yaml", "--split", "proof",
                     "--repeats", "1", "--runs", str(tmp_path / "r"),
                     "--evidence", str(tmp_path / "e")]) == 0
    before, after = sorted((tmp_path / "e").iterdir())
    assert main(["diff", str(before), str(after), "--out", str(tmp_path / "c")]) == 0
    (tmp_path / "roles.yaml").write_text("users:\n  tester: [approver]\n")
    assert main(["approve", str(tmp_path / "c"), "--roles", str(tmp_path / "roles.yaml")]) == 1


# signatures -------------------------------------------------------------------

needs_ssh = pytest.mark.skipif(shutil.which("ssh-keygen") is None, reason="no ssh-keygen")


def _key(tmp: Path, name: str) -> tuple[Path, Path]:
    key = tmp / name
    subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", name, "-f", str(key)],
                   check=True)
    return key, Path(str(key) + ".pub")


@needs_ssh
def test_signature_names_the_signer_and_breaks_on_change(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    pack = load_pack(PACK)
    s = Settings.model_validate({"name": "sim", "instructions": "x",
                                 "assistant": {"adapter": "scripted"},
                                 "retrieval": {"enabled": False}, "repeats": 1})
    run_dir, _ = run_pack(pack, s, tmp_path / "r", split="proof", limit=2)
    ev = write_evidence_pack(run_dir, pack, tmp_path / "ev")

    key, pub = _key(tmp_path, "jane")
    allowed = tmp_path / "allowed_signers"
    allowed.write_text(f'jane@bank.example namespaces="evidence-pack" {pub.read_text()}')
    sign(ev, key)
    ok, msg = verify_signature(ev, allowed)
    assert ok and "jane@bank.example" in msg
    assert verify(ev, allowed_signers=allowed).ok

    other, _ = _key(tmp_path, "mallory")
    sign(ev, other)
    ok, msg = verify_signature(ev, allowed)
    assert not ok and "not in the allowed signers" in msg

    sign(ev, key)
    ck = ev / "CHECKSUMS.json"
    ck.write_text(ck.read_text().replace('"algorithm"', '"algorithm" ', 1))
    ok, _ = verify_signature(ev, allowed)
    assert not ok
