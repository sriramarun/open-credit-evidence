# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The readable views — static HTML generated from the machine record.

Four readers, four views, plus the records they all link into:

- ``decision.html``        — model risk: go / go with conditions / no-go, and why
- ``failures.html``        — business owner: one card per kind of failure, with an example
- ``recommendations.html`` — what to change, who can, the settings patch, how to prove it
- ``regulation.html``      — compliance: evidences / contributes / does not cover
- ``vendor.html``          — what only the vendor can fix, with reproducible cases
- ``audit.html``           — the needs_audit queue, weakest first
- ``records.html``         — every answer and result; every number elsewhere links here

Rendering is deterministic (no clock, no randomness), so the verifier can
re-render and compare byte for byte. Registered as the last derivation step.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import yaml
from jinja2 import Environment, PackageLoader, StrictUndefined, pass_context, select_autoescape
from markupsafe import Markup

from evidence.derive import Inputs, step

NAV = [
    ("index.html", "Overview"), ("decision.html", "Decision"), ("failures.html", "Failures"),
    ("recommendations.html", "Changes"), ("regulation.html", "Regulation"),
    ("vendor.html", "Vendor"), ("audit.html", "Review queue"), ("records.html", "Records"),
]

CAUSE_LABEL = {
    "not_provided": "Facts never given to the assistant",
    "search_miss": "Search missed the facts",
    "miscalculated": "Figure worked out wrongly",
    "invented_figure": "Figure invented despite the right one being given",
    "skipped": "Fact seen and left out",
    "decoy_blamed": "Irrelevant field blamed",
    "wrong_lever": "Wrong or no way to change the outcome",
    "followed_injection": "Obeyed an instruction hidden in a document",
    "ungrounded_citation": "Cited a rule it was never given",
    "unclear": "Could not be placed by the rules",
}

STATUS_LABEL = {"go": "GO", "conditional": "CONDITIONAL", "no_go": "NO-GO",
                "insufficient": "TOO FEW RESULTS", "not_run": "NOT RUN"}

MITIGATION = {
    "followed_injection": "Instruct the assistant to treat documents as data, and turn on the "
                          "runtime guard's injection check. Neither makes the model itself "
                          "resistant.",
    "invented_figure": None,
    "ungrounded_citation": "Instruct the assistant to cite only what it was given. That limits "
                           "the damage; it does not stop the model inventing citations.",
}


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}"


def _vclass(decision: dict) -> str:
    if decision["simulated"]:
        return "v-SIM"
    return {"GO": "v-GO", "GO WITH CONDITIONS": "v-COND",
            "INCONCLUSIVE": "v-SIM"}.get(decision["verdict"], "v-NO")


class _BlockDumper(yaml.SafeDumper):
    """Multi-line strings as ``|`` blocks, the way a person writes them in a settings file."""


def _str(dumper: yaml.SafeDumper, data: str) -> yaml.Node:
    style = "|" if "\n" in data else None
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style=style)


_BlockDumper.add_representer(str, _str)


def _yaml_patch(p: dict) -> str:
    """Render a dotted setting as the YAML a person would paste into the settings file."""
    keys = p["setting"].split(".")
    obj: Any = p["value"]
    for k in reversed(keys):
        obj = {k: obj}
    return yaml.dump(obj, Dumper=_BlockDumper, sort_keys=False, allow_unicode=True,
                     width=88).rstrip()


@pass_context
def _agent_notes(ctx: Any, key: str) -> Markup:
    """Agent-written notes for one target, boxed and labelled. Nothing if none, or if the
    page has no notes in its context (change records, monitoring)."""
    notes = ctx.get("notes") or {}
    return Markup("").join(
        Markup('<div class="agent"><div class="who">Agent-written ({}, {}) — explanation '
               'only, not evidence</div>{}</div>').format(
            n["slot"].replace("_", " "), n["model_id"], n["text"])
        for n in notes.get(key, [])
    )


def _env() -> Environment:
    env = Environment(
        loader=PackageLoader("evidence", "report/templates"),
        autoescape=select_autoescape(["html", "j2"]),
        undefined=StrictUndefined, trim_blocks=True, lstrip_blocks=True,
    )
    env.globals.update(pct=_pct, vclass=_vclass, yaml_patch=_yaml_patch, agent_notes=_agent_notes,
                       cause_label=lambda c: CAUSE_LABEL.get(c, c),
                       status_label=lambda s: STATUS_LABEL.get(s, s),
                       case=lambda item_id: item_id.split(":")[2] if ":" in item_id else item_id)
    return env


def _cards(inp: Inputs) -> list[dict[str, Any]]:
    diag = inp.derived["diagnosis"]
    recs = {r["cause"]: r for r in inp.derived["recommendations"]["recommendations"]}
    t_by_sha = {t.sha256: t for t in inp.transcripts}
    first: dict[str, dict] = {}
    for d in diag["records"]:
        # the example is the omission result where there is one: it shows the most
        if d["cause"] not in first or (d["check"] == "material_omission"
                                       and first[d["cause"]]["check"] != "material_omission"):
            first[d["cause"]] = d
    same_answer: dict[str, dict[str, Any]] = defaultdict(dict)
    for d in diag["records"]:
        for k, v in d["detail"].items():
            same_answer[d["transcript_sha256"]].setdefault(k, v)
    cards = []
    for c in diag["causes"]:
        d = first[c["cause"]]
        t = t_by_sha[d["transcript_sha256"]]
        item = inp.items[d["item_id"]]
        det = {**same_answer[t.sha256], **d["detail"]}
        missing = [item.grading.omission_labels.get(r, r) for r in det.get("missing", [])]
        sources = sorted({" and ".join(alt.split("+"))
                          for alts in det.get("sources", {}).values() for alt in alts})
        retrieval_on = inp.settings.get("retrieval", {}).get("enabled", True)
        cards.append({
            **c,
            "why": _why(c["cause"], c["checks"]),
            "recommendation": recs[c["cause"]]["title"] if c["cause"] in recs else "",
            "example": {
                "case": d["item_id"].split(":")[2], "repeat": d["repeat"],
                "variant": item.tags.get("variant", ""), "sha": t.sha256[:12],
                "output": t.output, "missing": missing, "sources": sources,
                "retrieved": ([r.chunk_id for r in t.retrieved
                               if not r.renderer.startswith("corpus:")]
                              if retrieval_on else None),
                "figures": det.get("figures_not_in_file", []),
                "decoys": det.get("decoys", []),
            },
        })
    return cards


def _why(cause: str, checks: list[str]) -> str:
    from evidence.decide import MEANING

    return " ".join(MEANING[c] for c in checks if c in MEANING)


def _vendor(inp: Inputs) -> list[dict[str, Any]]:
    out = []
    t_by_sha = {t.sha256: t for t in inp.transcripts}
    for r in inp.derived["recommendations"]["recommendations"]:
        if not r["raise_with_vendor"]:
            continue
        recs = [d for d in inp.derived["diagnosis"]["records"] if d["cause"] == r["cause"]]
        cases, seen = [], set()
        for d in recs:
            case = d["item_id"].split(":")[2]
            if case not in seen:
                seen.add(case)
                cases.append({"case": case, "sha": t_by_sha[d["transcript_sha256"]].sha256[:12]})
        out.append({"cause": r["cause"], "title": CAUSE_LABEL[r["cause"]], "why": r["why"],
                    "results": r["addresses"]["results"], "items": r["addresses"]["items"],
                    "cases": cases, "mitigation": MITIGATION.get(r["cause"])})
    return out


@step("reports")
def _reports(inp: Inputs) -> dict[str, bytes]:
    env = _env()
    agg = inp.derived["aggregate"]
    diag = inp.derived["diagnosis"]
    cause_of = {d["result_id"]: d["cause"] for d in diag["records"]}
    by_cause: dict[str, list[dict]] = defaultdict(list)
    for d in diag["records"]:
        by_cause[d["cause"]].append(d)
    res_by_t: dict[str, list[dict]] = defaultdict(list)
    for r in inp.derived["results"]:
        res_by_t[r["transcript_sha256"]].append({**r, "cause": cause_of.get(r["result_id"])})
    transcripts = [{
        "item_id": t.item_id, "repeat": t.repeat, "sha": t.sha256[:12], "model": t.sut.model_id,
        "output": t.output, "results": res_by_t[t.sha256],
        "retrieved": [r.chunk_id for r in t.retrieved],
    } for t in inp.transcripts]

    ctx = {
        "run": inp.run, "agg": agg, "decision": inp.derived["decision"],
        "recs": inp.derived["recommendations"], "obligations": inp.obligations,
        "nav": NAV, "cards": _cards(inp), "vendor": _vendor(inp),
        "by_cause": dict(sorted(by_cause.items())), "transcripts": transcripts,
        "notes": __import__("evidence.slots", fromlist=["x"]).notes_by_target(inp.agent_notes),
        "model_ids": sorted({t.sut.model_id for t in inp.transcripts}),
        "endpoints": sorted({t.sut.endpoint or "?" for t in inp.transcripts}),
    }
    titles = dict(NAV)
    out = {}
    for page, _ in NAV:
        html = env.get_template(page + ".j2").render(**ctx, page=page, title=titles[page])
        out[f"reports/{page}"] = html.encode()
    return out
