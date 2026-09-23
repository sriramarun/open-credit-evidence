# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Stage 0, end to end: run → evidence pack → verify, and the tamper tests.

Uses the scripted assistant, so it runs offline in well under a second. The
scripted assistant's numbers are not evidence about anything; these tests only
prove the engine records, recomputes and refuses correctly.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence.evidence_pack import verify, write_evidence_pack
from evidence.evidence_pack.writer import write_checksums
from evidence.packs import PackTampered, load_pack
from evidence.runner import run_pack
from evidence.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "underwriter-sample"

pytestmark = pytest.mark.skipif(not (PACK / "items.jsonl").exists(), reason="pack not built")


@pytest.fixture(scope="module")
def pack():
    return load_pack(PACK)


@pytest.fixture
def sim(monkeypatch):
    monkeypatch.chdir(ROOT)  # settings refer to corpus/ relative to the repo root
    return load_settings(ROOT / "settings" / "sim-baseline.yaml")


@pytest.fixture
def evidence(tmp_path, pack, sim) -> Path:
    run_dir, _ = run_pack(pack, sim, tmp_path / "runs", split="proof", limit=6, repeats=2)
    return write_evidence_pack(run_dir, pack, tmp_path / "ev", attester="Test Attester")


def test_clean_pack_verifies(evidence):
    rep = verify(evidence)
    assert rep.ok, rep.render()


def test_changed_digit_is_rejected_and_named(evidence):
    agg_path = evidence / "aggregate.json"
    agg = json.loads(agg_path.read_text())
    agg["checks"]["material_omission"]["passed"] += 1
    agg_path.write_text(json.dumps(agg, indent=2, sort_keys=True) + "\n")
    rep = verify(evidence)
    assert not rep.ok
    text = rep.render()
    assert "aggregate.json: changed since the pack was written" in text
    assert "checks.material_omission.passed" in text


def test_changed_digit_with_regenerated_checksums_is_still_rejected(evidence):
    """The careful forger fixes the checksums too. Recomputation still catches it."""
    agg_path = evidence / "aggregate.json"
    agg = json.loads(agg_path.read_text())
    agg["checks"]["numeric_fidelity"]["pass_rate"] = 0.99
    agg_path.write_text(json.dumps(agg, indent=2, sort_keys=True) + "\n")
    write_checksums(evidence, attester="Forger", seal_key=None)
    rep = verify(evidence)
    assert not rep.ok
    assert any("checks.numeric_fidelity.pass_rate" in e and "recomputed" in e
               for e in rep.errors), rep.render()


def test_edited_transcript_is_rejected(evidence):
    path = evidence / "transcripts.jsonl"
    lines = path.read_text().splitlines()
    t = json.loads(lines[0])
    t["output"] = t["output"] + " The applicant exceeds the 40% policy limit."
    lines[0] = json.dumps(t)
    path.write_text("\n".join(lines) + "\n")
    write_checksums(evidence, attester=None, seal_key=None)
    rep = verify(evidence)
    assert not rep.ok
    assert any("transcript(s) altered" in e for e in rep.errors), rep.render()


def test_seal(tmp_path, pack, sim):
    run_dir, _ = run_pack(pack, sim, tmp_path / "runs", split="proof", limit=2, repeats=1)
    ev = write_evidence_pack(run_dir, pack, tmp_path / "ev", seal_key="k1")
    assert verify(ev, seal_key="k1").ok
    assert not verify(ev, seal_key="other").ok


def test_runner_resumes_without_repeating_calls(tmp_path, pack, sim):
    run_dir, m1 = run_pack(pack, sim, tmp_path, split="tune", limit=3, repeats=2)
    lines = (run_dir / "transcripts.jsonl").read_text().splitlines()
    (run_dir / "transcripts.jsonl").write_text("\n".join(lines[:2]) + "\n")  # "killed"
    _, m2 = run_pack(pack, sim, tmp_path, split="tune", limit=3, repeats=2)
    after = (run_dir / "transcripts.jsonl").read_text().splitlines()
    assert m2.calls_done == m2.calls_planned == 6
    assert len(after) == 6
    assert after[:2] == lines[:2]


def test_runner_refuses_changed_settings_under_same_run_id(tmp_path, pack, sim):
    run_pack(pack, sim, tmp_path, split="tune", limit=1, repeats=1, run_id="r")
    other = sim.model_copy(update={"instructions": "Different."})
    with pytest.raises(ValueError, match="different settings"):
        run_pack(pack, other, tmp_path, split="tune", limit=1, repeats=1, run_id="r")


def test_tampered_case_pack_is_refused(tmp_path):
    import shutil

    for f in PACK.iterdir():
        if f.is_file():
            shutil.copy(f, tmp_path / f.name)
    items = (tmp_path / "items.jsonl").read_text().replace("40%", "45%", 1)
    (tmp_path / "items.jsonl").write_text(items)
    with pytest.raises(PackTampered):
        load_pack(tmp_path)


def test_two_runs_differ_only_in_timestamps(tmp_path, pack, sim):
    """PLAN.md Week 4: same inputs twice, compare. Transcripts equal once timestamps go."""
    a, _ = run_pack(pack, sim, tmp_path, split="proof", limit=4, repeats=2, run_id="a")
    b, _ = run_pack(pack, sim, tmp_path, split="proof", limit=4, repeats=2, run_id="b")

    def strip(p):
        out = []
        for line in (p / "transcripts.jsonl").read_text().splitlines():
            d = json.loads(line)
            d.pop("started_at"), d.pop("run_id"), d.pop("latency_ms")
            out.append(d)
        return out

    assert strip(a) == strip(b)
    assert (a / "results.jsonl").read_text() == (b / "results.jsonl").read_text()


def test_not_exercised_injection_is_not_a_pass(tmp_path, pack, monkeypatch):
    monkeypatch.chdir(ROOT)
    s = load_settings(ROOT / "settings" / "sim-search-case-file.yaml")
    injected = [i for i in pack.items if i.tags["variant"] == "injected"][:3]
    ids = {i.item_id for i in injected}
    small = pack.__class__(root=pack.root, manifest=pack.manifest,
                           items=[i for i in pack.items if i.item_id in ids],
                           obligations=pack.obligations, items_sha256=pack.items_sha256)
    run_dir, _ = run_pack(small, s, tmp_path, repeats=1)
    ev = write_evidence_pack(run_dir, pack, tmp_path / "ev")
    agg = json.loads((ev / "aggregate.json").read_text())
    inj = agg["checks"]["injection_resistance"]
    assert inj["not_exercised"] == 3 and inj["passed"] == 0 and inj["pass_rate"] is None
