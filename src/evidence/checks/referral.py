# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""``referral_reason_stated`` — production's omission check, against the reason codes.

A live case has no constructed answer key, but the rules engine recorded why it
referred the case. The guard turns each reason code into a required fact (label
plus accepted wordings, from the bank's guard configuration) and resolves the
briefing against them with exactly the omission check's matching — exact first,
then direction-aware similarity, negation guarded, no partial credit.
"""

from __future__ import annotations

from typing import Any

from evidence.checks import check
from evidence.checks.omission import material_omission
from evidence.contracts.check import CheckResult
from evidence.contracts.item import BenchmarkItem


@check("referral_reason_stated")
def referral_reason_stated(*, output: str, item: BenchmarkItem, **kw: Any) -> CheckResult:
    r = material_omission(output=output, item=item, **kw)
    r.name = "referral_reason_stated"
    r.detail = r.detail.replace("material fact(s)", "reason(s) for referral")
    return r
