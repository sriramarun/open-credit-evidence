# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The built sample pack holds the properties the design depends on."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

from evidence.checks import run_checks
from evidence.contracts.item import BenchmarkItem

PACK = Path(__file__).resolve().parents[1] / "packs" / "underwriter-sample"
OUTCOME_WORDS = re.compile(
    r"\b(approve[ds]?|accepted|granted|declin(e|ed)|reject(ed)?|refus(e|ed)|"
    r"unsuccessful|turned down|denied|refer(red)?|manual review|escalated)\b",
    re.IGNORECASE,
)

pytestmark = pytest.mark.skipif(not (PACK / "items.jsonl").exists(),
                                reason="sample pack not built; run scripts/build_sample_pack.py")


def _items() -> list[BenchmarkItem]:
    return [BenchmarkItem.model_validate_json(line) for line in (PACK / "items.jsonl").open()]


def test_manifest_checksum_matches_items() -> None:
    m = json.loads((PACK / "manifest.json").read_text())
    assert m["items_sha256"] == hashlib.sha256((PACK / "items.jsonl").read_bytes()).hexdigest()
    assert m["ceiling"]["claimed"] is False


def test_every_item_is_a_referral_with_omission_targets() -> None:
    items = _items()
    assert len(items) == 20
    for it in items:
        assert it.grading.disposition == "refer"
        assert it.grading.omission_refs, it.item_id
        assert set(it.grading.omission_refs) <= set(it.grading.omission_labels)


def test_documents_never_state_the_outcome() -> None:
    for it in _items():
        for doc in it.context:
            assert not OUTCOME_WORDS.search(doc.content), (it.item_id, doc.renderer)


def test_answer_key_does_not_travel() -> None:
    def keys(obj: object) -> set[str]:
        out: set[str] = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                out.add(k)
                out |= keys(v)
        elif isinstance(obj, list):
            for v in obj:
                out |= keys(v)
        return out

    for line in (PACK / "items.jsonl").open():
        assert not {"contributions", "margin", "threshold", "score"} & keys(json.loads(line))
    # Flip refs carry field and direction only.
    for it in _items():
        for f in it.grading.flip_refs:
            assert set(f.model_dump()) == {"ref", "direction"}


def test_decoys_and_drivers_are_disjoint() -> None:
    for it in _items():
        g = it.grading
        assert not set(g.driver_refs) & set(g.decoy_refs), it.item_id


def test_negative_control_fails_on_every_real_item() -> None:
    """A briefing that mentions only strengths omits the driver on every referred case."""
    strengths_only = (
        "Strong applicant with a solid bureau score and a long credit file. Employment and "
        "income position are stable and income is verified. Recommend approval."
    )
    for it in _items():
        (r,) = run_checks(["material_omission"], output=strengths_only, item=it)
        assert not r.passed, it.item_id
