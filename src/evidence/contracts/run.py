# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""What a run is: which pack, which settings, which engine, how many calls.

Written once at the start of a run and updated when it finishes. Every number in
an evidence pack traces back to transcripts listed under one of these.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RunManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    pack_id: str
    pack_items_sha256: str
    settings_name: str
    settings_sha256: str
    corpus_sha256: str | None = None  # the law corpus version, if the settings use one
    engine_version: str
    engine_git: str | None = None
    repeats: int
    split: str | None = None  # "tune", "proof", or None for every case
    item_ids: list[str] = Field(default_factory=list)
    simulated: bool = False  # the assistant was the scripted test double
    started_at: str
    finished_at: str | None = None
    calls_planned: int = 0
    calls_done: int = 0
