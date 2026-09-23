# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""What the runner writes per item — the record every check and the evidence pack read.

One transcript per (item, repeat, system under test). It pins everything needed
to reproduce the call, keeps the full exchange, and — for RAG — records what was
retrieved, so an omission caused by retrieval can be told apart from one
caused by the model.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SUTPins(_Strict):
    """Enough to re-run the call and get the same answer, or know why not."""

    model_id: str
    prompt_version: str  # sha256 of the system prompt
    params: dict  # temperature, top_p, max_tokens, seed, enable_thinking …
    settings_sha256: str | None = None  # the settings file this call ran under
    endpoint: str | None = None  # where it ran: cloud, on-prem, or "simulated"


class Retrieved(_Strict):
    """One chunk RAG handed to the model. Empty list means no RAG."""

    renderer: str
    chunk_id: str
    score: float
    text: str


class Transcript(_Strict):
    item_id: str
    run_id: str
    repeat: int = 0
    sut: SUTPins

    system_prompt: str
    user_prompt: str
    retrieved: list[Retrieved] = Field(default_factory=list)

    output: str
    latency_ms: int
    tokens_in: int
    tokens_out: int
    provider_id: str | None = None  # the endpoint's own response id, if any

    simulated: bool = False  # produced by the scripted test double, not a real model
    started_at: str  # ISO 8601, UTC
    sha256: str  # over (item_id, repeat, sut, prompts, output) — content address

    @staticmethod
    def content_hash(
        item_id: str, repeat: int, sut: SUTPins, system_prompt: str, user_prompt: str, output: str
    ) -> str:
        blob = json.dumps(
            [item_id, repeat, sut.model_dump(), system_prompt, user_prompt, output],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def verify_hash(self) -> bool:
        return self.sha256 == self.content_hash(
            self.item_id, self.repeat, self.sut, self.system_prompt, self.user_prompt, self.output
        )
