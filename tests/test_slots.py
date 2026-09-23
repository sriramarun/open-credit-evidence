# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Agent slots: off by default; when on, notes are labelled, separate, figure-free, and
change no result."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evidence.evidence_pack import verify, write_evidence_pack
from evidence.packs import load_pack
from evidence.runner import run_pack
from evidence.settings import load_settings
from evidence.slots import annotate

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "packs" / "underwriter-sample"
pytestmark = pytest.mark.skipif(not (PACK / "items.jsonl").exists(), reason="pack not built")


class FakeNarrator:
    model_id = "fake-narrator"

    def narrate(self, cause: dict) -> str:
        return f"In plain words: {cause['explanation']}"


class NumberyProposer:
    model_id = "fake-proposer"

    def propose(self, rec: dict, settings: dict) -> str:
        return "This would lift the pass rate to 99%."  # a figure: must be rejected


@pytest.fixture
def pack_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.syspath_prepend(str(Path(__file__).parent))
    s = load_settings(ROOT / "settings" / "sim-baseline.yaml")
    pack = load_pack(PACK)
    run_dir, _ = run_pack(pack, s, tmp_path / "r", split="proof", repeats=1)
    return write_evidence_pack(run_dir, pack, tmp_path / "ev")


def test_slots_are_off_by_default():
    s = load_settings(ROOT / "settings" / "baseline.yaml")
    assert not any(s.agents.model_dump().values())


def test_notes_are_labelled_separate_and_change_no_result(pack_dir):
    before = {f: (pack_dir / f).read_text() for f in
              ("results.jsonl", "aggregate.json", "diagnosis.json", "decision.json")}
    notes = annotate(pack_dir, {"narrator": "test_slots:FakeNarrator",
                                "proposer": "test_slots:NumberyProposer"})
    for f, text in before.items():
        assert (pack_dir / f).read_text() == text, f"{f} changed"
    shown = [n for n in notes if n.status == "shown"]
    rejected = [n for n in notes if n.status != "shown"]
    assert shown and all(n.slot == "narrator" for n in shown)
    assert rejected and all("figure" in n.status for n in rejected)
    html = (pack_dir / "reports" / "failures.html").read_text()
    assert "Agent-written (narrator, fake-narrator)" in html
    assert "99%" not in (pack_dir / "reports" / "recommendations.html").read_text()
    assert verify(pack_dir).ok
    lines = (pack_dir / "agent_notes.jsonl").read_text().splitlines()
    assert len(lines) == len(notes) and json.loads(lines[0])["created_at"]
