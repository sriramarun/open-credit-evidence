# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""NVIDIA Build endpoints — the three models, pinned, behind one client.

Everything is served from ``https://integrate.api.nvidia.com/v1`` through the
OpenAI-compatible API. Nothing runs locally. The key comes from the environment
(``NVIDIA_API_KEY``) or a gitignored ``.env``; it is never in code.

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

BASE_URL = "https://integrate.api.nvidia.com/v1"

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
class ChatResponse:
    text: str
    model_id: str
    prompt_version: str  # sha256 of the system prompt, so runs pin it
    params: dict[str, Any]
    latency_ms: int
    tokens_in: int
    tokens_out: int
    raw_id: str | None = None


def _client():
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pip install openai") from exc
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        raise RuntimeError(
            "NVIDIA_API_KEY is not set. Generate one at build.nvidia.com -> Manage API Keys, "
            "then `export NVIDIA_API_KEY=...` or put it in a gitignored .env"
        )
    return OpenAI(base_url=BASE_URL, api_key=key)


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
    model_id = _pinned(MODELS[role])
    if thinking is None:
        thinking = role == "judge"
    params: dict[str, Any] = {
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "seed": seed,
    }
    extra: dict[str, Any] = {"chat_template_kwargs": {"enable_thinking": thinking}}
    client = _client()
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
    )


def embed(texts: list[str], *, input_type: str) -> list[list[float]]:
    """Embed with the retriever. ``input_type`` must be ``passage`` or ``query``."""
    if input_type not in ("passage", "query"):
        raise ValueError("input_type must be 'passage' (indexing) or 'query' (searching)")
    client = _client()
    resp = client.embeddings.create(
        model=_pinned(MODELS["embed"]),
        input=texts,
        encoding_format="float",
        extra_body={"input_type": input_type, "truncate": "END"},
    )
    return [d.embedding for d in resp.data]
