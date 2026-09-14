# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""What the runner writes per item — the record every check and the evidence pack read.

One transcript per (item, system under test). It pins everything needed to
reproduce the call, keeps the full exchange, and — for RAG — records what was
retrieved, so an omission caused by retrieval can be told apart from one
caused by the model.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SUTPins(_Strict):
    """Enough to re-run the call and get the same answer, or know why not."""

    model_id: str
    prompt_version: str  # sha256 of the system prompt
    params: dict  # temperature, top_p, max_tokens, seed, enable_thinking …


class Retrieved(_Strict):
    """One chunk RAG handed to the model. Empty list means no RAG."""

    renderer: str
    chunk_id: str
    score: float
    text: str


class Transcript(_Strict):
    item_id: str
    run_id: str
    sut: SUTPins

    system_prompt: str
    user_prompt: str
    retrieved: list[Retrieved] = Field(default_factory=list)

    output: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    provider_id: str | None = None  # the endpoint's own response id, if any

    started_at: str  # ISO 8601, UTC
    sha256: str  # over (item_id, sut, prompts, output) — content address
