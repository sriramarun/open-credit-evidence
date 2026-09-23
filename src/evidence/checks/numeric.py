# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""``numeric_fidelity`` — is every number in the briefing in the case file?

On 16 September, 8 of 10 real briefings stated a wrong debt-to-income ratio.
A wrong figure in a fluent paragraph is exactly what an underwriter will not
re-derive. So: every number the briefing states must appear in one of the case
documents, or be one of the derived figures the pack declares (a ratio that is
computable from the documents but printed in none of them).

Matching allows for rounding: a stated value counts if it is within 0.5, or
0.5%, of an allowed value — "47%" matches a derived 46.8.

Numbered-list markers ("1.", "2)") at the start of a line are not figures. A
duration in months may be restated in years ("176 months" as "14 years and 8
months").

What this check does NOT establish: that a number is attached to the right
thing. "Bureau score of 111" passes if 111 is the file age in months. It catches
invented and mis-computed figures, not mis-labelled ones. The evidence lists
each number and what it matched, so a reviewer can see.
"""

from __future__ import annotations

import re
from typing import Any

from evidence.checks import check
from evidence.contracts.check import CheckResult
from evidence.contracts.item import BenchmarkItem

# A number, not part of an identifier: "£21,100", "47%", "3.5", "21k". Excludes
# digits glued to letters on the left (APP000044, PL-2026.1 handled by the dash rule).
_NUM = re.compile(
    r"(?<![A-Za-z0-9\-.])(£|\$|€)?(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(\s?(?:k|K|m|bn)\b)?(%)?"
)


_MONTHS = re.compile(r"\b(\d+) months\b")

# "1." / "2)" opening a line is a list marker, not a figure.
_LIST_MARKER = re.compile(r"(?m)^[ \t>*_-]*(\d{1,2})[.)](?=\s)")


def _values(text: str) -> list[tuple[str, float]]:
    markers = {m.start(1) for m in _LIST_MARKER.finditer(text)}
    out = []
    for m in _NUM.finditer(text):
        if m.start(2) in markers:
            continue
        raw = m.group(0)
        v = float(m.group(2).replace(",", ""))
        suffix = (m.group(3) or "").strip().lower()
        v *= {"k": 1e3, "m": 1e6, "bn": 1e9}.get(suffix, 1)
        out.append((raw.strip(), v))
    return out


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= max(0.5, 0.005 * abs(b))


@check("numeric_fidelity")
def numeric_fidelity(*, output: str, item: BenchmarkItem, **_: Any) -> CheckResult:
    docs = item.documents_text()
    doc_values = {v for _, v in _values(docs)}
    # "176 months" may honestly be stated as "14 years and 8 months" or "over 14 years".
    for m in _MONTHS.finditer(docs):
        months = int(m.group(1))
        doc_values |= {months // 12, months % 12, round(months / 12, 1)}
    derived = item.grading.derived_numbers
    stated = _values(output)
    if not stated:
        return CheckResult(
            name="numeric_fidelity", passed=True, score=1.0,
            detail="the briefing states no figures",
        )

    evidence: list[dict[str, Any]] = []
    bad: list[str] = []
    for raw, v in stated:
        hit = next((d for d in doc_values if _close(v, d)), None)
        if hit is not None:
            evidence.append({"stated": raw, "value": v, "ok": True, "matched": "document",
                             "to": hit})
            continue
        dname = next((k for k, d in derived.items() if _close(v, d)), None)
        if dname is not None:
            evidence.append({"stated": raw, "value": v, "ok": True, "matched": f"derived:{dname}",
                             "to": derived[dname]})
            continue
        bad.append(raw)
        evidence.append({"stated": raw, "value": v, "ok": False, "matched": None,
                         "nearest_derived": {k: d for k, d in derived.items()}})

    ok = len(stated) - len(bad)
    passed = not bad
    detail = (
        f"all {len(stated)} figure(s) are in, or derivable from, the case file"
        if passed
        else f"{len(bad)} of {len(stated)} figure(s) not in the case file: {bad}"
    )
    return CheckResult(
        name="numeric_fidelity", passed=passed, score=ok / len(stated), detail=detail,
        evidence=evidence,
    )
