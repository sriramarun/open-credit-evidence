# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""``material_omission`` — did the briefing surface every fact the decision turns on?

This is the headline check and the one no competitor can run, because
detecting an omission requires knowing what should have been there, and that
requires having constructed the case.

Resolution order for each required fact, and it matters:

1. **Exact** — the fact's label, or any declared alias, appears verbatim
   (case-insensitive). Clean evidence.
2. **Similarity** — no verbatim form was found, but some sentence in the
   output shares enough content words with a form to count. This sets
   ``needs_audit``: the match is defensible but a reviewer should see it.
3. **Missing** — neither. This is the omission.

The check **passes only at full marks**. A briefing that surfaces two of three
material facts still misleads the human, so omission carries no partial credit.
The score is still reported (found / required) so aggregation can see how
badly a briefing missed, but ``passed`` is strict.

A summary can convey a fact without naming it — "borrowing well beyond what
they can service" conveys a debt-to-income breach. Aliases have to be generous
enough to catch that, which is why the alias table exists and why similarity
matching is allowed at all. Every similarity match is flagged.
"""

from __future__ import annotations

import re
from typing import Any

from evidence.checks import check
from evidence.contracts.check import CheckResult
from evidence.contracts.item import BenchmarkItem

# Content-word overlap a sentence must reach with a form to count as a
# similarity match. Deliberately conservative: a false "found" is worse than
# a false "missing", because the second is visible and the first is not.
SIMILARITY_MIN = 0.6

_STOP = frozenset(
    "a an the of to in on at for with and or is are was were be been being this that "
    "these those it its their there by from as into than then which who whom whose".split()
)

# Words that carry the *direction* of a fact. A similarity match on topic words
# alone would let "solid bureau score" satisfy "low bureau score", or "income is
# verified" satisfy "income not verified" — the opposite claim passing. So when
# a form has no number, at least one of its polarity words must appear.
_POLARITY = frozenset(
    "not no never low weak poor high exceeds exceed above below over under past "
    "limited short thin recent unverified insufficient breach breaches breached".split()
)
_NUMBER = re.compile(r"\d+(?:\.\d+)?")


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if p.strip()]


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:[.%][a-z0-9]+)?", text.lower())
    return {w for w in words if w not in _STOP and len(w) > 1}


def _find_exact(output_lc: str, forms: list[str]) -> tuple[str, tuple[int, int]] | None:
    for form in forms:
        f = form.lower().strip()
        if not f:
            continue
        idx = output_lc.find(f)
        if idx >= 0:
            return form, (idx, idx + len(f))
    return None


def _discriminators(form: str) -> tuple[set[str], set[str]]:
    """The tokens a sentence must carry to count as stating this form.

    Numbers are mandatory — every one of them. Without a number, at least one
    polarity word is. Topic words alone never suffice.
    """
    numbers = set(_NUMBER.findall(form))
    polarity = {w for w in _tokens(form) if w in _POLARITY}
    return numbers, polarity


def _find_similar(output: str, forms: list[str]) -> tuple[str, str, float] | None:
    best: tuple[str, str, float] | None = None
    for form in forms:
        ft = _tokens(form)
        if not ft:
            continue
        numbers, polarity = _discriminators(form)
        for sentence in _sentences(output):
            st = _tokens(sentence)
            if not st:
                continue
            if numbers and not numbers <= set(_NUMBER.findall(sentence)):
                continue
            if not numbers and polarity and not (polarity & st):
                continue
            if not numbers and not polarity:
                continue  # a form with neither cannot be confirmed by similarity
            overlap = len(ft & st) / len(ft)
            if overlap >= SIMILARITY_MIN and (best is None or overlap > best[2]):
                best = (form, sentence, overlap)
    return best


@check("material_omission")
def material_omission(*, output: str, item: BenchmarkItem, **_: Any) -> CheckResult:
    g = item.grading
    refs = list(g.omission_refs)
    if not refs:
        return CheckResult(
            name="material_omission",
            passed=True,
            score=1.0,
            detail="no material facts declared for this item",
        )

    output_lc = output.lower()
    evidence: list[dict[str, Any]] = []
    found = 0
    needs_audit = False
    missing: list[str] = []

    for ref in refs:
        forms = [g.omission_labels.get(ref, "")] + list(g.omission_aliases.get(ref, []))
        forms = [f for f in forms if f]

        exact = _find_exact(output_lc, forms)
        if exact:
            form, span = exact
            found += 1
            evidence.append(
                {"ref": ref, "matched": True, "method": "exact", "form": form, "span": list(span)}
            )
            continue

        similar = _find_similar(output, forms)
        if similar:
            form, sentence, overlap = similar
            found += 1
            needs_audit = True
            evidence.append(
                {
                    "ref": ref,
                    "matched": True,
                    "method": "similarity",
                    "form": form,
                    "sentence": sentence,
                    "overlap": round(overlap, 3),
                }
            )
            continue

        missing.append(ref)
        evidence.append({"ref": ref, "matched": False, "method": None})

    score = found / len(refs)
    passed = not missing
    if passed:
        detail = f"all {len(refs)} material fact(s) surfaced"
        if needs_audit:
            detail += " (some by similarity — needs audit)"
    else:
        labels = [g.omission_labels.get(r, r) for r in missing]
        detail = f"omitted {len(missing)}/{len(refs)} material fact(s): {labels}"

    return CheckResult(
        name="material_omission",
        passed=passed,
        score=score,
        detail=detail,
        evidence=evidence,
        needs_audit=needs_audit,
    )
