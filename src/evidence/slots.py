# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Agent slots — places an AI helper can be plugged in later. All off by default.

The rule the whole product rests on: **the checks decide, an agent may explain,
a person acts.** So an agent never touches a verdict, a result, or a number.
Four slots, each with a plain non-agent default that already runs:

- ``diagnoser`` — default: rule-based root causes (diagnose.py). An agent would
  read the transcripts the rules marked "unclear".
- ``proposer`` — default: a template patch per lever (recommend.py). An agent
  would draft a more specific settings change.
- ``audit_helper`` — default: the review queue, weakest first. An agent would
  argue the case *against* each weak match.
- ``narrator`` — default: template sentences in the views. An agent would write
  plainer explanatory text on the cards.

Turn one on in the settings file (``agents: {audit_helper: "pkg.module:Class"}``)
and run ``evidence annotate <pack>``. What the agent writes:

- goes into ``agent_notes.jsonl`` — never into check results or the aggregate;
- carries its provenance (slot, model, prompt version, trace id);
- is shown labelled "agent-written" wherever it appears;
- **is rejected if it contains a figure**. Numbers come from the record, never
  from an agent; a note with a digit in it is kept, marked rejected, and not shown.

A proposer's change is a proposal like any other: it is accepted only through
``evidence diff`` on PROOF cases. Before an agent replaces a default in anyone's
workflow, it should be shown to beat that default on a measured task.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from evidence.runner import now

SLOTS = ("diagnoser", "proposer", "audit_helper", "narrator")


class AgentNote(BaseModel):
    model_config = ConfigDict(extra="forbid")
    slot: str
    target: str  # what it is about: a result id, a cause, a queue entry
    text: str
    model_id: str
    prompt_version: str
    trace_id: str | None = None
    created_at: str
    status: str = "shown"  # "shown" | "rejected: <why>"


class Diagnoser(Protocol):
    def diagnose(self, record: dict, transcript: dict, item: dict) -> str | None: ...


class Proposer(Protocol):
    def propose(self, recommendation: dict, settings: dict) -> str | None: ...


class AuditHelper(Protocol):
    def argue_against(self, entry: dict) -> str | None: ...


class Narrator(Protocol):
    def narrate(self, cause: dict) -> str | None: ...


def load_slot(spec: str) -> Any:
    mod, _, cls = spec.partition(":")
    if not cls:
        raise ValueError(f"agent slot must be 'package.module:Class', got {spec!r}")
    return getattr(importlib.import_module(mod), cls)()


def _note(slot: str, target: str, text: str, agent: Any) -> AgentNote:
    status = "shown"
    if re.search(r"\d", text):
        status = "rejected: contains a figure — numbers come from the record, not from an agent"
    return AgentNote(
        slot=slot, target=target, text=text.strip(),
        model_id=getattr(agent, "model_id", type(agent).__name__),
        prompt_version=getattr(agent, "prompt_version", "n/a"),
        trace_id=getattr(agent, "last_trace_id", None),
        created_at=now(), status=status,
    )


def annotate(pack_dir: str | Path, agents: dict[str, str | None]) -> list[AgentNote]:
    """Run the enabled slots over a finished evidence pack; rewrite its derived views."""
    from evidence.derive import derive, load_inputs
    from evidence.evidence_pack.writer import write_checksums

    root = Path(pack_dir)
    j = lambda n: json.loads((root / n).read_text())  # noqa: E731
    diag, recs, agg = j("diagnosis.json"), j("recommendations.json"), j("aggregate.json")
    settings = __import__("yaml").safe_load((root / "settings.yaml").read_text())
    transcripts = {json.loads(x)["sha256"]: json.loads(x)
                   for x in (root / "transcripts.jsonl").read_text().splitlines() if x}
    items = {json.loads(x)["item_id"]: json.loads(x)
             for x in (root / "items.jsonl").read_text().splitlines() if x}

    notes: list[AgentNote] = []
    for slot, spec in agents.items():
        if not spec:
            continue
        agent = load_slot(spec)
        if slot == "diagnoser":
            for d in diag["records"]:
                if d["cause"] == "unclear":
                    t = agent.diagnose(d, transcripts[d["transcript_sha256"]], items[d["item_id"]])
                    if t:
                        notes.append(_note(slot, d["result_id"], t, agent))
        elif slot == "proposer":
            for r in recs["recommendations"]:
                t = agent.propose(r, settings)
                if t:
                    notes.append(_note(slot, f"cause:{r['cause']}", t, agent))
        elif slot == "audit_helper":
            for q in agg["needs_audit"]:
                if q["anchor"] == "wording":
                    t = agent.argue_against(q)
                    if t:
                        notes.append(_note(slot, f"{q['result_id']}:{q['ref']}", t, agent))
        elif slot == "narrator":
            for c in diag["causes"]:
                t = agent.narrate(c)
                if t:
                    notes.append(_note(slot, f"cause:{c['cause']}", t, agent))
        else:
            raise ValueError(f"unknown slot {slot!r}; one of {SLOTS}")

    (root / "agent_notes.jsonl").write_text(
        "".join(n.model_dump_json() + "\n" for n in notes))
    for rel, body in derive(load_inputs(root)).items():  # views now show the notes, labelled
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(body)
    attester = json.loads((root / "attestation.json").read_text()).get("attester")
    write_checksums(root, attester=attester, seal_key=os.environ.get("EVIDENCE_SEAL_KEY"))
    return notes


def notes_by_target(notes: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for n in notes:
        if n["status"] == "shown":
            out.setdefault(n["target"], []).append(n)
    return out


# A reference agent, OFF by default: argues against weak matches using the judge
# endpoint. It exists to show the interface, not as a recommendation to enable it.
class ChatAuditHelper:
    model_id = "judge-endpoint"
    SYSTEM = ("You review a claim that a sentence conveys a required fact. Make the strongest "
              "case, in two sentences, that it does NOT. Do not use any numbers.")
    prompt_version = hashlib.sha256(SYSTEM.encode()).hexdigest()[:16]
    last_trace_id: str | None = None

    def argue_against(self, entry: dict) -> str | None:
        from evidence.adapters.nvidia_build import chat

        r = chat("judge", system=self.SYSTEM,
                 user=f"Required fact: {entry['form']}\nSentence credited: {entry['sentence']}",
                 max_tokens=200, thinking=False)
        self.model_id, self.last_trace_id = r.model_id, r.raw_id
        return r.text
