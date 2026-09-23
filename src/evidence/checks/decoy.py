# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""``decoy_citation`` — did the briefing blame a field that has no bearing on the outcome?

Decoys are known by construction: the case generator gives them no path to the
outcome. Mentioning a decoy is fine ("employed at Harrow Estates for 63 months").
Blaming one is not ("the short time in role is a concern") — it points the
underwriter at noise.

The rule: a decoy is *blamed* when a sentence names it and also carries a blame
word (concern, risk, weakness, against, because …). Sentence-level, deliberately
simple, and every hit lists the sentence so a reviewer can overrule it.
"""

from __future__ import annotations

import re
from typing import Any

from evidence.checks import check
from evidence.contracts.check import CheckResult
from evidence.contracts.item import BenchmarkItem

BLAME = re.compile(
    r"\b(concern(?:s|ing)?|risk(?:s|y)?|weak(?:ness|nesses)?|negative(?:ly)?|against|"
    r"because|due to|driver|drives|driven|factor|issue|problem|worr(?:y|ying|ies)|adverse|"
    r"red flag|counts against|raises|undermines|detracts)\b",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n+", text) if p.strip()]


@check("decoy_citation")
def decoy_citation(*, output: str, item: BenchmarkItem, **_: Any) -> CheckResult:
    g = item.grading
    hits: list[dict[str, Any]] = []
    for sentence in _sentences(output):
        if not BLAME.search(sentence):
            continue
        for ref in g.decoy_refs:
            for alias in g.decoy_aliases.get(ref, []):
                if re.search(rf"\b{re.escape(alias)}\b", sentence, re.IGNORECASE):
                    hits.append({"ref": ref, "alias": alias, "sentence": sentence,
                                 "blame_word": BLAME.search(sentence).group(0)})
                    break
    refs = sorted({h["ref"] for h in hits})
    passed = not hits
    return CheckResult(
        name="decoy_citation",
        passed=passed,
        score=1.0 if passed else 0.0,
        detail="no decoy field blamed" if passed else f"blamed decoy field(s): {refs}",
        evidence=hits,
    )
