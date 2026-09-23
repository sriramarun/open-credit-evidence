# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""``citation_grounded`` — is every rule or article the briefing cites in what it was given?

The assistant is handed the case file and, from the law corpus, a few reference
passages. If it cites "Article 22" and no Article 22 was in front of it, the
citation came from the model's memory — or nowhere. An underwriter will not
check; an auditor will.

Needs no answer key, only the prompt, so it runs in validation and in production
alike. "Article 14(4)(a)" is grounded if "Article 14" appears in the prompt;
"Art. 14" and "Article 14" are the same citation.

Not applicable when the briefing cites nothing: an answer without citations is
not wrong, and counting it as a pass would inflate the rate.
"""

from __future__ import annotations

import re
from typing import Any

from evidence.checks import check
from evidence.contracts.check import CheckResult
from evidence.contracts.item import BenchmarkItem
from evidence.corpus import find_citations


def _norm(s: str) -> str:
    s = re.sub(r"\bArt\.?\s*(?=\d)", "Article ", s, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", s).strip().lower()


def _base(citation: str) -> str:
    """"Article 14(4)(a)" -> "article 14"."""
    return _norm(re.sub(r"(\(\w+\))+$", "", citation))


@check("citation_grounded")
def citation_grounded(
    *, output: str, item: BenchmarkItem, prompt: str | None = None, **_: Any
) -> CheckResult:
    cited = find_citations(output)
    if not cited:
        return CheckResult(name="citation_grounded", passed=True, score=1.0, applicable=False,
                           detail="the briefing cites no rule or article")
    given = _norm(prompt if prompt is not None else item.documents_text())
    evidence = []
    for c in cited:
        base = _base(c)
        ok = re.search(rf"(?<![\w.]){re.escape(base)}(?!\d)", given) is not None
        evidence.append({"citation": c, "grounded": ok})
    bad = [e["citation"] for e in evidence if not e["grounded"]]
    return CheckResult(
        name="citation_grounded",
        passed=not bad,
        score=(len(cited) - len(bad)) / len(cited),
        detail=(f"all {len(cited)} citation(s) appear in what the assistant was given" if not bad
                else f"cited {bad}, which the assistant was never given"),
        evidence=evidence,
    )
