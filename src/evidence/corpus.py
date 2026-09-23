# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The law and policy corpus — passages the assistant may cite.

A folder of markdown files, one passage each, with a small header:

    ---
    id: eu-ai-act-art-14
    title: EU AI Act, Article 14 — Human oversight (summary)
    cites: ["Article 14", "Art. 14", "Art 14"]
    version: "2024/1689"
    ---
    Passage text …

``cites`` lists the strings that count as citing this passage. The corpus has a
version (the folder's content hash) and every run manifest records it, because
regulations move and a pack must say which text it was checked against.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from evidence.contracts.item import ItemContext


@dataclass(frozen=True)
class Passage:
    id: str
    title: str
    text: str
    cites: list[str] = field(default_factory=list)
    version: str = ""


@dataclass(frozen=True)
class Corpus:
    passages: list[Passage]
    sha256: str

    def by_id(self, pid: str) -> Passage | None:
        return next((p for p in self.passages if p.id == pid), None)

    def as_context(self) -> list[ItemContext]:
        """Each passage as a one-section document, so the case-file retriever can search it."""
        return [
            ItemContext(renderer=f"corpus:{p.id}", variant="corpus",
                        content=f"## {p.title}\n\n{p.text}")
            for p in self.passages
        ]

    def resolve(self, citation: str) -> Passage | None:
        """The passage a citation refers to. "Article 14(4)(a)" resolves to a passage citing
        "Article 14"; "Article 140" does not."""
        c = citation.lower().strip()
        for p in self.passages:
            for s in p.cites:
                if re.search(rf"(?<![\w.]){re.escape(s.lower())}(?![\w])", c):
                    return p
        return None


_FRONT = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.S)


def load_corpus(path: str | Path) -> Corpus:
    root = Path(path)
    passages: list[Passage] = []
    digest = hashlib.sha256()
    for f in sorted(root.glob("*.md")):
        raw = f.read_text()
        digest.update(f.name.encode() + b"\0" + raw.encode())
        m = _FRONT.match(raw)
        if not m:
            raise ValueError(f"{f}: missing --- header ---")
        head = yaml.safe_load(m.group(1)) or {}
        passages.append(
            Passage(
                id=str(head["id"]),
                title=str(head.get("title", head["id"])),
                text=m.group(2).strip(),
                cites=[str(s) for s in head.get("cites", [])],
                version=str(head.get("version", "")),
            )
        )
    if not passages:
        raise ValueError(f"{root}: no passages")
    return Corpus(passages=passages, sha256=digest.hexdigest())


# Things that look like a citation of a rule or an article, in any domain.
CITATION = re.compile(
    r"\b(?:Article|Art\.?)\s*\d+(?:\(\d+\))*(?:\([a-z]\))?"
    r"|\bAnnex\s+[IVX]+\b"
    r"|\b[A-Z]{2,5}-\d{4}\.\d+\b",
)


def find_citations(text: str) -> list[str]:
    return list(dict.fromkeys(m.group(0) for m in CITATION.finditer(text)))
