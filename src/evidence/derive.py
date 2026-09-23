# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Everything in an evidence pack that is computed rather than recorded.

An evidence pack has two kinds of file:

- **Inputs** — what happened and what it was judged against: the case pack
  (``items.jsonl``, its manifest, obligations), the run (``run_manifest.json``,
  ``settings.yaml``, ``transcripts.jsonl``) and the bank's ``thresholds.yaml``.
- **Derived** — everything computed from the inputs: check results, the
  aggregate, diagnosis, recommendations, and every readable view.

``derive(inputs)`` is one pure function from the first to the second. The writer
calls it to build the pack; the verifier calls it again and compares. So no
number in any view can be typed by hand: if it doesn't come out of ``derive``,
the verifier rejects the pack and names it.

Later stages register more derivation steps; each sees the outputs of the
steps before it.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from evidence.aggregate import aggregate
from evidence.contracts.item import BenchmarkItem
from evidence.contracts.transcript import Transcript

INPUT_FILES = (
    "items.jsonl", "pack_manifest.json", "obligations.yaml",
    "run_manifest.json", "settings.yaml", "transcripts.jsonl", "thresholds.yaml",
)


@dataclass
class Inputs:
    items: dict[str, BenchmarkItem]
    pack_manifest: dict
    obligations: dict
    run: dict
    settings: dict
    transcripts: list[Transcript]
    thresholds: dict
    agent_notes: list[dict] = field(default_factory=list)  # optional; see evidence.slots
    derived: dict[str, Any] = field(default_factory=dict)  # objects from earlier steps


def load_inputs(root: str | Path) -> Inputs:
    root = Path(root)
    items = {}
    for line in (root / "items.jsonl").read_text().splitlines():
        if line.strip():
            it = BenchmarkItem.model_validate_json(line)
            items[it.item_id] = it
    return Inputs(
        items=items,
        pack_manifest=json.loads((root / "pack_manifest.json").read_text()),
        obligations=yaml.safe_load((root / "obligations.yaml").read_text()) or {},
        run=json.loads((root / "run_manifest.json").read_text()),
        settings=yaml.safe_load((root / "settings.yaml").read_text()),
        transcripts=[Transcript.model_validate_json(line)
                     for line in (root / "transcripts.jsonl").read_text().splitlines()
                     if line.strip()],
        thresholds=yaml.safe_load((root / "thresholds.yaml").read_text()) or {},
        agent_notes=[json.loads(x) for x in (root / "agent_notes.jsonl").read_text().splitlines()
                     if x.strip()] if (root / "agent_notes.jsonl").exists() else [],
    )


def dump_json(obj: Any) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


Step = Callable[[Inputs], dict[str, bytes]]
STEPS: list[tuple[str, Step]] = []


def step(name: str) -> Callable[[Step], Step]:
    def register(fn: Step) -> Step:
        STEPS.append((name, fn))
        return fn
    return register


@step("results")
def _results(inp: Inputs) -> dict[str, bytes]:
    from evidence.runner import check_transcript

    results: list[dict] = []
    for t in inp.transcripts:
        results.extend(check_transcript(t, inp.items[t.item_id]))
    inp.derived["results"] = results
    body = "".join(json.dumps(r, sort_keys=True) + "\n" for r in results)
    return {"results.jsonl": body.encode()}


@step("aggregate")
def _aggregate(inp: Inputs) -> dict[str, bytes]:
    agg = aggregate(inp.derived["results"], inp.items, inp.run, inp.obligations)
    inp.derived["aggregate"] = agg
    return {"aggregate.json": dump_json(agg)}


def _load_later_steps() -> None:
    # Importing registers. Order matters: each step may read what earlier ones derived.
    import importlib

    for mod in ("evidence.diagnose", "evidence.recommend", "evidence.decide", "evidence.report"):
        try:
            importlib.import_module(mod)
        except ModuleNotFoundError as exc:
            if exc.name != mod:
                raise


# Steps run in this order whatever order their modules were imported in; each may read
# what earlier ones derived. Unknown steps run last, in registration order.
ORDER = ["results", "aggregate", "diagnosis", "recommendations", "decision", "reports"]


def derive(inp: Inputs) -> dict[str, bytes]:
    _load_later_steps()
    rank = {name: i for i, name in enumerate(ORDER)}
    out: dict[str, bytes] = {}
    for _, fn in sorted(STEPS, key=lambda s: rank.get(s[0], len(ORDER))):
        out.update(fn(inp))
    return out
