# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The assistant under test, behind one interface.

The engine never talks to a model directly. It builds the prompt from the item
and the settings file, hands it to an adapter, and records what came back:

- ``openai``   — any OpenAI-compatible endpoint (NVIDIA Build, a NIM, vLLM, a vendor gateway)
- ``scripted`` — the built-in test double (``adapters/scripted.py``). Deterministic, offline,
                 and never evidence about any real assistant; every record it produces
                 is marked ``simulated``.
- ``callable`` — "package.module:function(system, user) -> str", for a vendor SDK or an
                 agent that is not an HTTP endpoint

Prompt assembly lives here, not in the adapters, so that every adapter sees the
same thing for the same settings — which is what makes two runs comparable.
"""

from __future__ import annotations

import hashlib
import importlib
import time
from dataclasses import dataclass, field
from typing import Any

from evidence.adapters import rag
from evidence.contracts.item import BenchmarkItem, ItemContext
from evidence.contracts.transcript import Retrieved
from evidence.corpus import Corpus, load_corpus
from evidence.settings import Settings


@dataclass(frozen=True)
class Prompt:
    system: str
    user: str
    retrieved: list[Retrieved]


@dataclass(frozen=True)
class Reply:
    text: str
    model_id: str
    endpoint: str
    params: dict[str, Any]
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    provider_id: str | None = None
    simulated: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


def selected_documents(item: BenchmarkItem, settings: Settings) -> list[ItemContext]:
    wanted = settings.context.documents
    docs = [c for c in item.context if not wanted or c.renderer in wanted]
    if wanted:
        missing = set(wanted) - {c.renderer for c in item.context}
        if missing:
            raise ValueError(f"{item.item_id}: settings ask for documents it lacks: {missing}")
    return docs


_corpus_cache: dict[str, Corpus] = {}


def _corpus(settings: Settings) -> Corpus | None:
    if not settings.corpus.path or settings.corpus.top_k <= 0:
        return None
    if settings.corpus.path not in _corpus_cache:
        _corpus_cache[settings.corpus.path] = load_corpus(settings.corpus.path)
    return _corpus_cache[settings.corpus.path]


def build_prompt(item: BenchmarkItem, settings: Settings, extra_user: str = "") -> Prompt:
    """System = the bank's instructions. User = the task, the template, the case file,
    any regulatory passages, and (for guard retries) the pointer."""
    docs = selected_documents(item, settings)
    r = settings.retrieval
    if r.enabled:
        retrieved = rag.retrieve(
            r.query or item.prompt, docs, k=r.top_k, method=r.method, chunking=r.chunking
        )
        case_file = rag.as_prompt(retrieved)
    else:
        retrieved = []
        case_file = "\n\n---\n\n".join(f"[{d.renderer}]\n{d.content.strip()}" for d in docs)

    parts = [item.prompt.strip()]
    if settings.output_template:
        parts.append("Format your answer as follows:\n" + settings.output_template.strip())
    parts.append("CASE FILE\n\n" + case_file)

    corpus = _corpus(settings)
    if corpus:
        refs = rag.retrieve(
            r.query or item.prompt, corpus.as_context(), k=settings.corpus.top_k,
            method="lexical", chunking="section",
        )
        retrieved = retrieved + refs
        parts.append("REFERENCE PASSAGES\n\n" + rag.as_prompt(refs))
    if extra_user:
        parts.append(extra_user.strip())
    return Prompt(
        system=settings.instructions.strip(), user="\n\n".join(parts), retrieved=retrieved
    )


def prompt_version(system: str) -> str:
    return hashlib.sha256(system.encode()).hexdigest()[:16]


def call(prompt: Prompt, settings: Settings, *, item: BenchmarkItem, repeat: int) -> Reply:
    a = settings.assistant
    if a.adapter == "scripted":
        from evidence.adapters.scripted import respond

        return respond(prompt, settings, item=item, repeat=repeat)
    if a.adapter == "callable":
        return _call_callable(prompt, settings)
    return _call_openai(prompt, settings)


def _call_openai(prompt: Prompt, settings: Settings) -> Reply:
    from evidence.adapters import nvidia_build as nb

    a = settings.assistant
    ep = nb.endpoint_for(a.role)
    if a.base_url or a.model:
        ep = nb.Endpoint(role=a.role, base_url=(a.base_url or ep.base_url).rstrip("/"),
                         model_id=nb._pinned(a.model or ep.model_id))
    p = a.params
    params = {"temperature": p.temperature, "top_p": p.top_p, "max_tokens": p.max_tokens,
              "seed": p.seed}
    client = nb._client(ep)
    t0 = time.perf_counter()
    resp = client.chat.completions.create(
        model=ep.model_id,
        messages=[{"role": "system", "content": prompt.system},
                  {"role": "user", "content": prompt.user}],
        extra_body={"chat_template_kwargs": {"enable_thinking": p.thinking}},
        **params,
    )
    usage = resp.usage
    return Reply(
        text=resp.choices[0].message.content or "",
        model_id=ep.model_id,
        endpoint=ep.base_url,
        params=params | {"enable_thinking": p.thinking},
        latency_ms=int((time.perf_counter() - t0) * 1000),
        tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
        tokens_out=getattr(usage, "completion_tokens", 0) or 0,
        provider_id=getattr(resp, "id", None),
    )


def _call_callable(prompt: Prompt, settings: Settings) -> Reply:
    spec = settings.assistant.callable
    if not spec or ":" not in spec:
        raise ValueError("assistant.callable must be 'package.module:function'")
    mod, fn = spec.split(":", 1)
    func = getattr(importlib.import_module(mod), fn)
    t0 = time.perf_counter()
    text = func(prompt.system, prompt.user)
    return Reply(
        text=str(text),
        model_id=settings.assistant.model or spec,
        endpoint=f"callable:{spec}",
        params=settings.assistant.params.model_dump(),
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )
