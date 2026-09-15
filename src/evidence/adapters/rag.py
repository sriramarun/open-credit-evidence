# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Minimal retrieval over a case file.

Splits each document on its section headings, embeds the sections as
``passage``, embeds the question as ``query``, and returns the top-k by cosine.
Deliberately small: the case file is two short documents, so this exists to
reproduce the deployment shape — the assistant *selects* what to read — and
to record what was retrieved, not to solve a hard search problem.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from evidence.adapters.nvidia_build import embed
from evidence.contracts.item import ItemContext
from evidence.contracts.transcript import Retrieved


@dataclass(frozen=True)
class Chunk:
    renderer: str
    chunk_id: str
    text: str


def chunk_documents(context: list[ItemContext]) -> list[Chunk]:
    """One chunk per markdown section (``## heading``), heading kept with its body."""
    chunks: list[Chunk] = []
    for doc in context:
        parts = re.split(r"(?m)^(?=## )", doc.content)
        # parts[0] is the title block; keep it so the reference and score survive
        for i, part in enumerate(p.strip() for p in parts if p.strip()):
            chunks.append(Chunk(doc.renderer, f"{doc.renderer}#{i}", part))
    return chunks


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve(question: str, context: list[ItemContext], *, k: int = 3) -> list[Retrieved]:
    """Top-k sections for ``question``, in rank order, with scores."""
    chunks = chunk_documents(context)
    vecs = embed([c.text for c in chunks], input_type="passage")
    q = embed([question], input_type="query")[0]
    scored = sorted(
        ((_cosine(v, q), c) for v, c in zip(vecs, chunks, strict=True)),
        key=lambda t: -t[0],
    )
    return [
        Retrieved(renderer=c.renderer, chunk_id=c.chunk_id, score=round(s, 4), text=c.text)
        for s, c in scored[:k]
    ]


def as_prompt(retrieved: list[Retrieved]) -> str:
    """What the assistant is actually handed under RAG — only what was retrieved."""
    return "\n\n---\n\n".join(f"[{r.chunk_id}]\n{r.text}" for r in retrieved)
