# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""A live referral, as the bank's systems hand it to the guard.

In production there is no answer key: the case was not constructed. What the
bank does have is why its rules engine referred the case — the reason codes, with
the value that tripped each one — and the figures the rules engine computed.
That is a partial answer key: whatever else a briefing says, it must state the
reasons the case was referred.

This is the contract the bank's integration team implements.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from evidence.contracts.item import ItemContext


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReasonCode(_Strict):
    code: str  # e.g. "AFF-01"
    rule: str = ""  # e.g. "Debt service above 40% of gross income"
    value: str = ""  # what tripped it, e.g. "46.5%"
    limit: str = ""  # e.g. "40%"


class Referral(_Strict):
    referral_id: str
    received_at: str | None = None  # ISO 8601; the monitoring report groups by day
    reason_codes: list[ReasonCode]
    documents: list[ItemContext]
    # Figures the rules engine computed, by name. numeric_fidelity accepts them.
    computed: dict[str, float] = Field(default_factory=dict)
