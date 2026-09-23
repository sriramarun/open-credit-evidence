# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The settings file — everything the bank can change about the assistant under test.

A bank does not own the vendor's model. What it does control is what it tells
the model, what it hands the model, how the model searches the case file, and
which of the vendor's models it uses. All of that lives in one YAML file, so
that "change one setting and re-run" is an edit, not a code change, and so that
every transcript can name the exact settings it ran under by hash.

    name: baseline
    assistant: {adapter: openai, role: assistant, params: {temperature: 0.0, seed: 7}}
    instructions: |
      You are supporting an underwriter ...
    context: {documents: [application_form, bureau_summary, lending_policy]}
    retrieval: {enabled: true, method: lexical, chunking: section, top_k: 3}
    repeats: 3
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssistantParams(_Strict):
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 1200
    seed: int | None = 7
    thinking: bool = False


class AssistantSettings(_Strict):
    # openai   — any OpenAI-compatible endpoint (NVIDIA Build, a NIM, vLLM, a vendor gateway)
    # scripted — the built-in test double; its results are never evidence
    # callable — "package.module:function" taking (system, user) and returning text
    adapter: Literal["openai", "scripted", "callable"] = "openai"
    role: str = "assistant"  # which EVIDENCE_<ROLE>_* variables resolve the endpoint
    base_url: str | None = None  # overrides the role's endpoint
    model: str | None = None  # overrides the role's model
    callable: str | None = None
    profile: str | None = None  # scripted adapter only: which simulated behaviour
    params: AssistantParams = Field(default_factory=AssistantParams)


class ContextSettings(_Strict):
    # Which of the case's documents the assistant is given, by renderer name.
    # An empty list means all of them.
    documents: list[str] = Field(default_factory=list)


class RetrievalSettings(_Strict):
    enabled: bool = True
    method: Literal["lexical", "embed"] = "lexical"
    chunking: Literal["section", "table_row"] = "section"
    top_k: int = 3
    query: str | None = None  # defaults to the item's own prompt


class CorpusSettings(_Strict):
    path: str | None = None  # folder of law / policy passages
    top_k: int = 0  # passages added to the prompt; 0 disables


class AgentSettings(_Strict):
    """Optional agent plug-ins. All off by default; see evidence.slots."""

    diagnoser: str | None = None
    proposer: str | None = None
    audit_helper: str | None = None
    narrator: str | None = None


class Settings(_Strict):
    name: str
    description: str = ""
    assistant: AssistantSettings = Field(default_factory=AssistantSettings)
    instructions: str
    output_template: str | None = None
    context: ContextSettings = Field(default_factory=ContextSettings)
    retrieval: RetrievalSettings = Field(default_factory=RetrievalSettings)
    corpus: CorpusSettings = Field(default_factory=CorpusSettings)
    repeats: int = 3
    agents: AgentSettings = Field(default_factory=AgentSettings)

    @property
    def simulated(self) -> bool:
        return self.assistant.adapter == "scripted"

    def canonical(self) -> dict:
        return self.model_dump(mode="json")

    def sha256(self) -> str:
        blob = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()

    def to_yaml(self) -> str:
        return yaml.safe_dump(self.canonical(), sort_keys=False, allow_unicode=True)


def load_settings(path: str | Path) -> Settings:
    data = yaml.safe_load(Path(path).read_text())
    return Settings.model_validate(data)


def changed_fields(a: Settings, b: Settings) -> list[dict]:
    """Every setting that differs between two runs, as dotted paths. Feeds the change log."""

    def flat(d: object, prefix: str = "") -> dict[str, object]:
        out: dict[str, object] = {}
        if isinstance(d, dict):
            for k, v in d.items():
                out |= flat(v, f"{prefix}{k}.")
        else:
            out[prefix.rstrip(".")] = d
        return out

    fa, fb = flat(a.canonical()), flat(b.canonical())
    skip = {"name", "description"}
    return [
        {"setting": k, "before": fa.get(k), "after": fb.get(k)}
        for k in sorted(set(fa) | set(fb))
        if k not in skip and fa.get(k) != fb.get(k)
    ]
