# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Stages 1–2: diagnosis, recommendations, decision and the readable views.

Run on the scripted assistant, whose flaws are known, so the tests can say what
the diagnosis must find. Not evidence about any real assistant.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from evidence.evidence_pack import verify, write_evidence_pack
from evidence.packs import load_pack
from evidence.runner import run_pack
from evidence.settings import load_settings

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "underwriter-sample"
pytestmark = pytest.mark.skipif(not (PACK / "items.jsonl").exists(), reason="pack not built")


def _pack_for(settings_name: str, tmp: Path, monkeypatch, thresholds: str | None = None) -> Path:
    monkeypatch.chdir(ROOT)
    pack = load_pack(PACK)
    s = load_settings(ROOT / "settings" / f"{settings_name}.yaml")
    run_dir, _ = run_pack(pack, s, tmp / "runs", split="proof", repeats=2)
    return write_evidence_pack(run_dir, pack, tmp / "ev", thresholds=thresholds)


@pytest.fixture
def baseline(tmp_path, monkeypatch) -> Path:
    return _pack_for("sim-baseline", tmp_path, monkeypatch)


def _j(ev: Path, name: str) -> dict:
    return json.loads((ev / name).read_text())


def test_baseline_diagnosis_finds_the_scripted_flaws(baseline):
    causes = {c["cause"] for c in _j(baseline, "diagnosis.json")["causes"]}
    assert {"miscalculated", "skipped", "decoy_blamed", "followed_injection"} <= causes


def test_top_recommendation_hands_in_the_computed_figures(baseline):
    top = _j(baseline, "recommendations.json")["recommendations"][0]
    assert top["cause"] == "miscalculated"
    (patch,) = top["patch"]
    assert patch["setting"] == "context.documents"
    assert "referral_record" in patch["value"]


def test_injection_is_raised_with_the_vendor(baseline):
    recs = _j(baseline, "recommendations.json")
    assert "followed_injection" in recs["vendor_findings"]
    assert "Obeyed an instruction hidden in a document" in (
        baseline / "reports" / "vendor.html").read_text()


def test_search_variant_is_diagnosed_as_search(tmp_path, monkeypatch):
    ev = _pack_for("sim-search-case-file", tmp_path, monkeypatch)
    diag = _j(ev, "diagnosis.json")
    omission = [d for d in diag["records"] if d["check"] == "material_omission"]
    assert omission and all(d["cause"] == "search_miss" for d in omission)
    (rec,) = [r for r in _j(ev, "recommendations.json")["recommendations"]
              if r["cause"] == "search_miss"]
    assert rec["patch"][0] == {**rec["patch"][0], "setting": "retrieval.enabled", "value": False}


def test_simulated_run_is_never_a_verdict(baseline):
    d = _j(baseline, "decision.json")
    assert d["verdict"] == "NOT EVIDENCE — SIMULATED ASSISTANT"
    assert d["would_be"] == "NO-GO"
    for page in (baseline / "reports").glob("*.html"):
        assert "Simulated assistant" in page.read_text(), page.name


def test_the_banks_thresholds_decide(tmp_path, monkeypatch):
    lenient = tmp_path / "lenient.yaml"
    lenient.write_text(
        "checks:\n" + "".join(f"  {c}: {{go: 0.0, conditional: 0.0}}\n" for c in (
            "material_omission", "numeric_fidelity", "decoy_citation", "flip_accuracy",
            "injection_resistance"))
        + "min_exercised: 1\nrepeat_agreement_min: 0.0\n"
    )
    ev = _pack_for("sim-baseline", tmp_path, monkeypatch, thresholds=str(lenient))
    assert _j(ev, "decision.json")["would_be"] == "GO"


def test_every_number_link_lands_on_a_record(baseline):
    """The traceability promise: every link into records.html resolves."""
    records = (baseline / "reports" / "records.html").read_text()
    ids = set(re.findall(r'id="([^"]+)"', records))
    for page in (baseline / "reports").glob("*.html"):
        for target in re.findall(r'href="records\.html#([^"]+)"', page.read_text()):
            assert target in ids, (page.name, target)


def test_reports_are_part_of_what_the_verifier_recomputes(baseline):
    page = baseline / "reports" / "decision.html"
    page.write_text(page.read_text().replace("NO-GO", "GO", 1))
    from evidence.evidence_pack.writer import write_checksums

    write_checksums(baseline, attester=None, seal_key=None)
    rep = verify(baseline)
    assert not rep.ok
    assert any("reports/decision.html" in e for e in rep.errors)


def test_review_queue_is_weakest_first(baseline):
    q = _j(baseline, "aggregate.json")["needs_audit"]
    anchors = [x["anchor"] for x in q]
    assert anchors == sorted(anchors, key=lambda a: a != "wording")
