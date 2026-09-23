# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Minimal retrieval over a case file.

Splits each document into chunks, scores them against a question, and returns
the top-k. Deliberately small: the case file is a few short documents, so this
exists to reproduce the deployment shape — the assistant *selects* what to read —
and to record what was retrieved, not to solve a hard search problem.

Chunk ids are stable and readable: ``<renderer>#<section-slug>`` for a whole
section, ``<renderer>#<section-slug>#r<n>`` for one table row. A pack's
``omission_sources`` use the section form, so diagnosis can ask "was the section
holding this fact ever handed to the model?" with a prefix match.

Two scoring methods, chosen in the settings file:

- ``lexical`` — word overlap weighted by rarity. No network, fully repeatable.
- ``embed``   — cosine similarity with the embedding model.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from evidence.contracts.item import ItemContext
from evidence.contracts.transcript import Retrieved


@dataclass(frozen=True)
class Chunk:
    renderer: str
    chunk_id: str
    text: str


def slug(heading: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", heading.lower()).strip("-") or "section"


def _sections(doc: ItemContext) -> list[tuple[str, str]]:
    """(slug, text) per ``## heading`` section; the title block is ``title``."""
    parts = [p.strip() for p in re.split(r"(?m)^(?=## )", doc.content) if p.strip()]
    out: list[tuple[str, str]] = []
    for part in parts:
        m = re.match(r"## (.+)", part)
        out.append((slug(m.group(1)) if m else "title", part))
    return out


def chunk_documents(context: list[ItemContext], *, chunking: str = "section") -> list[Chunk]:
    """Split documents into chunks. ``section`` keeps each section whole; ``table_row``
    makes every table row its own chunk, prefixed by its section heading so it still
    reads on its own."""
    chunks: list[Chunk] = []
    for doc in context:
        for sec, text in _sections(doc):
            base = f"{doc.renderer}#{sec}"
            if chunking != "table_row":
                chunks.append(Chunk(doc.renderer, base, text))
                continue
            lines = text.splitlines()
            heading = lines[0] if lines else ""
            sep = re.compile(r"^\|[-| :]+\|$")
            # A table's header row is the line directly above its |---| separator.
            headers = {i - 1 for i, ln in enumerate(lines) if sep.match(ln)}
            rows = [
                ln for i, ln in enumerate(lines)
                if ln.startswith("|") and not sep.match(ln) and i not in headers
            ]
            prose = [ln for ln in lines[1:] if ln.strip() and not ln.startswith("|")]
            if prose or not rows:
                chunks.append(Chunk(doc.renderer, base, "\n".join([heading, *prose]).strip()))
            for n, row in enumerate(rows):
                chunks.append(Chunk(doc.renderer, f"{base}#r{n}", f"{heading}\n{row}"))
    return chunks


_STOP = frozenset(
    "a an the of to in on at for with and or is are was were be been this that it its "
    "what why how would need from as by".split()
)


def _tokens(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1]


def _lexical_scores(question: str, chunks: list[Chunk]) -> list[float]:
    docs = [Counter(_tokens(c.text)) for c in chunks]
    n = len(docs)
    df: Counter[str] = Counter()
    for d in docs:
        df.update(d.keys())
    q = set(_tokens(question))
    scores = []
    for d in docs:
        length = sum(d.values()) or 1
        s = sum(math.log(1 + n / df[t]) * (1 + math.log(d[t])) for t in q if t in d)
        scores.append(s / math.sqrt(length))
    return scores


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _embed_scores(question: str, chunks: list[Chunk]) -> list[float]:
    from evidence.adapters.nvidia_build import embed

    vecs = embed([c.text for c in chunks], input_type="passage")
    q = embed([question], input_type="query")[0]
    return [_cosine(v, q) for v in vecs]


def retrieve(
    question: str,
    context: list[ItemContext],
    *,
    k: int = 3,
    method: str = "embed",
    chunking: str = "section",
) -> list[Retrieved]:
    """Top-k chunks for ``question``, in rank order, with scores. Ties keep document order."""
    chunks = chunk_documents(context, chunking=chunking)
    if not chunks:
        return []
    scores = _embed_scores(question, chunks) if method == "embed" else _lexical_scores(
        question, chunks
    )
    ranked = sorted(range(len(chunks)), key=lambda i: (-scores[i], i))[:k]
    return [
        Retrieved(
            renderer=chunks[i].renderer,
            chunk_id=chunks[i].chunk_id,
            score=round(scores[i], 4),
            text=chunks[i].text,
        )
        for i in ranked
    ]


def as_prompt(retrieved: list[Retrieved]) -> str:
    """What the assistant is actually handed under RAG — only what was retrieved."""
    return "\n\n---\n\n".join(f"[{r.chunk_id}]\n{r.text}" for r in retrieved)
