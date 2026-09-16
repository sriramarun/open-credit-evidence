# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""NVIDIA endpoints — the three models, pinned, behind one client.

Default is NVIDIA Build, ``https://integrate.api.nvidia.com/v1``, through the
OpenAI-compatible API. Any role can be pointed at a self-hosted NIM instead
(same API, different URL) with two environment variables, so the switch from
cloud to on-prem is a ``.env`` change and nothing else::

    EVIDENCE_ASSISTANT_BASE_URL=http://rtx-3se-05-36:8000/v1
    EVIDENCE_ASSISTANT_MODEL=nvidia/nemotron-3.5-lightning

Likewise ``EVIDENCE_JUDGE_*`` and ``EVIDENCE_EMBED_*``. Every response records
the endpoint it came from, so a transcript can always say whether a briefing was
produced in the cloud or on the team's own hardware. The Build key comes from
``NVIDIA_API_KEY`` or a gitignored ``.env``; a local NIM needs no key.

Model choices, confirmed on the catalogue 14 Sep 2026:

- **assistant**  ``nvidia/nemotron-3.5-lightning-30b-a3b`` — 30B MoE, 3B active,
  1M context, current (Aug 2026). Chosen over Super because Super's free
  endpoint is deprecated on 2 October, five days before the final.
- **judge**      ``nvidia/nemotron-3-ultra-550b-a55b`` — 550B MoE. Never the model
  under test. Thinking mode on, because a judge should show its working.
- **embed**      ``nvidia/nemotron-3-embed-1b`` — the retriever behind RAG.
  Requires ``input_type`` of ``passage`` (indexing) or ``query`` (searching);
  the catalogue warns that getting this wrong costs retrieval accuracy badly.

Account limit at time of writing: 40 requests per minute. The runner must
respect that.
"""

from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

BASE_URL = "https://integrate.api.nvidia.com/v1"
BUILD_HOST = "integrate.api.nvidia.com"

MODELS: dict[str, str] = {
    "assistant": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "judge": "nvidia/nemotron-3-ultra-550b-a55b",
    "embed": "nvidia/nemotron-3-embed-1b",
}

# Do not use. Free endpoint deprecated 2026-10-02 — before the final on 10-07.
DEPRECATED: dict[str, str] = {
    "nvidia/nemotron-3-super-120b-a12b": "deprecated 2026-10-02",
}


@dataclass(frozen=True)
class Endpoint:
    role: str
    base_url: str
    model_id: str

    @property
    def is_build(self) -> bool:
        return urlparse(self.base_url).hostname == BUILD_HOST


@dataclass(frozen=True)
class ChatResponse:
    text: str
    model_id: str
    prompt_version: str  # sha256 of the system prompt, so runs pin it
    params: dict[str, Any]
    latency_ms: int
    tokens_in: int
    tokens_out: int
    raw_id: str | None = None
    endpoint: str = BASE_URL  # where it ran — cloud or on-prem


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass


def endpoint_for(role: str) -> Endpoint:
    """Resolve where ``role`` runs: ``EVIDENCE_<ROLE>_BASE_URL`` / ``_MODEL``, else Build."""
    if role not in MODELS:
        raise KeyError(f"unknown role {role!r}; one of {sorted(MODELS)}")
    _load_env()
    key = role.upper()
    base_url = os.environ.get(f"EVIDENCE_{key}_BASE_URL", "").strip() or BASE_URL
    model_id = os.environ.get(f"EVIDENCE_{key}_MODEL", "").strip() or MODELS[role]
    return Endpoint(role=role, base_url=base_url.rstrip("/"), model_id=_pinned(model_id))


def _bypass_proxy(base_url: str) -> None:
    """A self-hosted NIM must not be routed through the cluster's HTTP proxy."""
    host = urlparse(base_url).hostname or ""
    if not host or host == BUILD_HOST:
        return
    for var in ("NO_PROXY", "no_proxy"):
        current = os.environ.get(var, "")
        if host not in current.split(","):
            os.environ[var] = f"{current},{host}" if current else host


def _client(ep: Endpoint):
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pip install openai") from exc
    if ep.is_build:
        key = os.environ.get("NVIDIA_API_KEY")
        if not key:
            raise RuntimeError(
                "NVIDIA_API_KEY is not set. Generate one at build.nvidia.com -> Manage API Keys, "
                "then `export NVIDIA_API_KEY=...` or put it in a gitignored .env"
            )
    else:
        _bypass_proxy(ep.base_url)
        key = os.environ.get("NVIDIA_API_KEY") or "local"
    return OpenAI(base_url=ep.base_url, api_key=key)


def _pinned(model_id: str) -> str:
    if model_id in DEPRECATED:
        raise ValueError(f"{model_id}: {DEPRECATED[model_id]}")
    return model_id


def chat(
    role: str,
    system: str,
    user: str,
    *,
    temperature: float = 0.0,
    top_p: float = 1.0,
    max_tokens: int = 2048,
    seed: int | None = 7,
    thinking: bool | None = None,
) -> ChatResponse:
    """One pinned, recorded call. ``role`` is ``assistant`` or ``judge``."""
    ep = endpoint_for(role)
    model_id = ep.model_id
    if thinking is None:
        thinking = role == "judge"
    params: dict[str, Any] = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "seed": seed,
    }
    extra: dict[str, Any] = {"chat_template_kwargs": {"enable_thinking": thinking}}
    client = _client(ep)
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=model_id,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        extra_body=extra,
        **params,
    )
    ms = int((time.perf_counter() - t0) * 1000)
    usage = resp.usage
    return ChatResponse(
        text=resp.choices[0].message.content or "",
        model_id=model_id,
        prompt_version=hashlib.sha256(system.encode()).hexdigest()[:16],
        params=params | {"enable_thinking": thinking},
        latency_ms=ms,
        tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
        tokens_out=getattr(usage, "completion_tokens", 0) or 0,
        raw_id=getattr(resp, "id", None),
        endpoint=ep.base_url,
    )


def embed(texts: list[str], *, input_type: str) -> list[list[float]]:
    """Embed with the retriever. ``input_type`` must be ``passage`` or ``query``."""
    if input_type not in ("passage", "query"):
        raise ValueError("input_type must be 'passage' (indexing) or 'query' (searching)")
    ep = endpoint_for("embed")
    client = _client(ep)
    resp = client.embeddings.create(
        model=ep.model_id,
        input=texts,
        encoding_format="float",
        extra_body={"input_type": input_type, "truncate": "END"},
    )
    return [d.embedding for d in resp.data]
