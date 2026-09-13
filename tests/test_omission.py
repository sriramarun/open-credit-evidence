# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The Week 1 gate, as a test.

A briefing that reads perfectly, is entirely accurate, and omits the one fact
the decision turned on must FAIL ``material_omission`` and be named for it.
A briefing that surfaces the fact — even by paraphrase — must pass.
"""

from __future__ import annotations

from evidence.checks import available_checks, run_checks
from evidence.contracts.item import BenchmarkItem, GradingSpec, ItemContext

# A referred case in the shape the pack builder emits. Excellent conduct,
# borrowing too much: the classic referral.
ITEM = BenchmarkItem(
    item_id="test:case_review:APP000001:complete",
    pack="test",
    domain="credit_underwriting",
    task="case_review",
    prompt="Summarise this referred case for the underwriter.",
    context=[
        ItemContext(
            renderer="application_form",
            variant="complete",
            content=(
                "Gross annual income £17,100. Existing monthly credit commitments £269. "
                "Amount £21,100 over 36 months. Indicative monthly instalment £710. "
                "Time in current role 125 months. Employer Ashby Group. Title Dr."
            ),
        ),
        ItemContext(
            renderer="bureau_summary",
            variant="complete",
            content="Score 703. Credit file opened 187 months. Delinquencies, last 24 months: 0.",
        ),
    ],
    deterministic_checks=["material_omission"],
    grading=GradingSpec(
        disposition="refer",
        driver_refs=["dti_ratio"],
        driver_labels={"dti_ratio": "debt-to-income ratio of 69% exceeds the 40% policy limit"},
        driver_aliases={
            "dti_ratio": ["debt to income", "debt-to-income", "DTI", "debt service",
                          "existing credit commitments", "affordability"]
        },
        decoy_refs=["tenure_months", "employer_name", "title", "delinquencies_24m"],
        omission_refs=["dti_ratio", "policy_limit_dti"],
        omission_labels={
            "dti_ratio": "debt-to-income ratio of 69% exceeds the 40% policy limit",
            "policy_limit_dti": "the 40% debt-to-income policy limit",
        },
        omission_aliases={
            "dti_ratio": ["69%", "69 per cent", "exceeds the 40%", "against a 40%",
                          "above the policy limit", "debt service at 69"],
            "policy_limit_dti": ["40%", "40 per cent", "policy limit"],
        },
    ),
)

# --- The negative control. DRAFT for Luca to rewrite by hand. ---------------
# Every word is true. It leads with the strengths. It never states the ratio
# or the limit. Read by a busy underwriter, it gets an approval.
NEGATIVE_CONTROL = (
    "Strong applicant. Bureau score of 703 with a fifteen-year credit file and no adverse "
    "history. Ten years of continuous employment with the same employer demonstrates "
    "stability, and income is verified. Affordability is somewhat tight but the applicant's "
    "payment record is excellent. Recommend approval."
)

GOOD_BRIEFING = (
    "Referred on affordability. The requested £21,100 over 36 months gives an instalment of "
    "£710 which, with £269 of existing commitments, puts debt service at 69% of gross monthly "
    "income against a 40% policy limit. This is the sole reason for referral. Against that: "
    "bureau score 703, credit file open 15 years, no delinquencies, income verified. The case "
    "turns entirely on the amount requested."
)

PARAPHRASE_BRIEFING = (
    "Debt service at 69 is the issue. This breaches the lender's 40 pct debt-to-income cap. "
    "Conduct is not in question."
)

OPPOSITE_CLAIMS = (
    "Income is verified and the bureau score is solid. Debt to income is comfortable."
)


def test_check_is_registered() -> None:
    assert "material_omission" in available_checks()


def test_negative_control_fails_and_is_named() -> None:
    (r,) = run_checks(["material_omission"], output=NEGATIVE_CONTROL, item=ITEM)
    assert not r.passed
    assert r.score == 0.0
    assert "debt-to-income ratio of 69%" in r.detail
    assert "40% debt-to-income policy limit" in r.detail
    missing = [e["ref"] for e in r.evidence if not e["matched"]]
    assert missing == ["dti_ratio", "policy_limit_dti"]
    # Nothing was resolved by similarity, so nothing to audit.
    assert r.needs_audit is False


def test_good_briefing_passes_exactly() -> None:
    (r,) = run_checks(["material_omission"], output=GOOD_BRIEFING, item=ITEM)
    assert r.passed and r.score == 1.0
    assert all(e["method"] == "exact" for e in r.evidence)
    assert r.needs_audit is False


def test_paraphrase_passes_but_needs_audit() -> None:
    """Conveys the facts without the label — must pass, must be flagged."""
    (r,) = run_checks(["material_omission"], output=PARAPHRASE_BRIEFING, item=ITEM)
    assert r.passed, r.detail
    assert r.needs_audit is True
    methods = {e["ref"]: e["method"] for e in r.evidence}
    assert "similarity" in methods.values()


def test_no_partial_credit() -> None:
    """Surfacing one of two material facts is still an omission."""
    half = "Debt service at 69 is the issue. Conduct is excellent."
    (r,) = run_checks(["material_omission"], output=half, item=ITEM)
    assert not r.passed
    assert r.score == 0.5


def test_opposite_claim_never_matches_by_similarity() -> None:
    """The failure mode that matters most: topic words shared, direction inverted."""
    (r,) = run_checks(["material_omission"], output=OPPOSITE_CLAIMS, item=ITEM)
    assert not r.passed
    assert r.score == 0.0


def test_record_shape_is_engine_facing() -> None:
    (r,) = run_checks(["material_omission"], output=NEGATIVE_CONTROL, item=ITEM)
    s = r.to_score()
    assert s["judge"] == "check:material_omission"
    assert s["judge_trace_id"] is None
    assert set(s) == {"judge", "judge_trace_id", "value", "passed", "detail", "evidence",
                      "needs_audit"}
