# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""What every check returns.

A deterministic check is a judge with perfect agreement. It therefore carries
no ``judge_trace_id`` and needs no validation study — and the evidence pack
says so rather than leaving a reader to assume it.

``needs_audit`` is mandatory reporting. It is set whenever a match was
resolved by similarity rather than exactly. The evidence pack surfaces the
count of such results; burying it is how a reviewer stops trusting the rest.

``applicable`` is False when the check could not be exercised on this
transcript — e.g. a planted instruction that search never handed to the model.
Such a result is neither a pass nor a fail and is counted separately; reporting
it as a pass would claim resistance that was never tested.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    name: str
    passed: bool
    score: float  # 0.0 – 1.0
    detail: str  # human-readable and defensible
    evidence: list[dict[str, Any]] = field(default_factory=list)
    needs_audit: bool = False
    applicable: bool = True

    def to_score(self) -> dict[str, Any]:
        """Engine-facing record, as it lands in results and the evidence pack."""
        return {
            "judge": f"check:{self.name}",
            "judge_trace_id": None,
            "value": self.score,
            "passed": self.passed,
            "detail": self.detail,
            "evidence": self.evidence,
            "needs_audit": self.needs_audit,
            "applicable": self.applicable,
        }
