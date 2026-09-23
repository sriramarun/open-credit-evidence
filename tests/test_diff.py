# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Stage 3: proving a change — accept, reject, no effect — and the change record's integrity.

Scripted assistant throughout; these test the comparison, not any real change.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence.diff import compare, verify_change, write_change_record
from evidence.evidence_pack import write_evidence_pack
from evidence.packs import load_pack
from evidence.runner import run_pack
from evidence.settings import Settings, load_settings

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "underwriter-sample"
pytestmark = pytest.mark.skipif(not (PACK / "items.jsonl").exists(), reason="pack not built")


@pytest.fixture
def make(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    pack = load_pack(PACK)

    def _make(settings: Settings, split: str = "proof", run_id: str | None = None) -> Path:
        run_dir, m = run_pack(pack, settings, tmp_path / "runs", split=split, repeats=2,
                              run_id=run_id)
        return write_evidence_pack(run_dir, pack, tmp_path / "ev" / m.run_id)

    return _make


def sim(name: str) -> Settings:
    return load_settings(ROOT / "settings" / f"{name}.yaml")


def test_handing_in_computed_figures_is_accepted(make):
    c = compare(make(sim("sim-baseline")), make(sim("sim-with-review-triggers")))
    assert c["verdict"] == "ACCEPT"
    assert [s["setting"] for s in c["settings_changed"]] == ["context.documents"]
    by = {r["check"]: r for r in c["checks"]}
    assert by["numeric_fidelity"]["status"] == "improved"
    assert by["numeric_fidelity"]["hurt"] == 0
    assert any("simulated" in w for w in c["warnings"])


def test_removing_the_policy_is_rejected(make):
    base = sim("sim-baseline")
    worse = base.model_copy(update={
        "name": "sim-no-policy",
        "context": base.context.model_copy(
            update={"documents": ["application_form", "bureau_summary"]}),
        "corpus": base.corpus.model_copy(update={"top_k": 0}),
    })
    c = compare(make(base), make(worse))
    assert c["verdict"] == "REJECT"
    assert any(r["status"] == "regressed" for r in c["checks"])


def test_identical_settings_have_no_effect(make):
    s = sim("sim-baseline")
    c = compare(make(s, run_id="a"), make(s, run_id="b"))
    assert c["verdict"] == "NO EFFECT"
    assert c["settings_changed"] == []


def test_tune_split_is_warned(make):
    c = compare(make(sim("sim-baseline"), split="tune"),
                make(sim("sim-with-review-triggers"), split="tune"))
    assert any("not on PROOF cases" in w for w in c["warnings"])


def test_change_record_verifies_and_catches_tampering(make, tmp_path):
    a, b = make(sim("sim-baseline")), make(sim("sim-with-review-triggers"))
    out = write_change_record(a, b, tmp_path / "change")
    assert verify_change(out).ok

    cmp_path = out / "comparison.json"
    c = json.loads(cmp_path.read_text())
    c["verdict"] = "ACCEPT" if c["verdict"] != "ACCEPT" else "REJECT"
    cmp_path.write_text(json.dumps(c))
    rep = verify_change(out)
    assert not rep.ok and any("verdict" in e for e in rep.errors), rep.render()


def test_change_record_notices_a_swapped_pack(make, tmp_path):
    a, b = make(sim("sim-baseline")), make(sim("sim-with-review-triggers"))
    out = write_change_record(a, b, tmp_path / "change")
    # rewrite the "after" pack from a different run into the same folder
    other = make(sim("sim-baseline"), run_id="other")
    import shutil

    shutil.rmtree(b)
    shutil.copytree(other, b)
    rep = verify_change(out)
    assert not rep.ok


# a callable assistant: anything that is not an HTTP endpoint -------------------

def echo_assistant(system: str, user: str) -> str:
    return "Referred on affordability; debt service exceeds the 40% policy limit."


def test_callable_adapter(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    s = Settings(name="callable", instructions="x",
                 assistant={"adapter": "callable", "callable": "test_diff:echo_assistant"},
                 context={"documents": []}, retrieval={"enabled": False}, repeats=1)
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    run_dir, m = run_pack(load_pack(PACK), s, tmp_path, split="proof", limit=2)
    t = json.loads((run_dir / "transcripts.jsonl").read_text().splitlines()[0])
    assert t["sut"]["endpoint"] == "callable:test_diff:echo_assistant"
    assert "exceeds the 40% policy limit" in t["output"]
    assert m.calls_done == 2
