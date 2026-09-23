# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Proving a change works — before and after, case by case, on PROOF cases.

    evidence diff evidence/baseline-proof-… evidence/with-review-triggers-proof-…

Compares two evidence packs run on the same cases with different settings, and
writes a change record: what changed in the settings, what happened to every
check, and whether the change is accepted.

**Paired, not pooled.** For each case and each check, the share of repeats that
passed before and after. The change *helped* a case if that share went up, *hurt*
it if it went down. The mean change across cases gets a 95% interval from the
spread of per-case changes — so a gain smaller than the assistant's own
run-to-run wobble is not mistaken for an improvement.

**The rule** (``thresholds.yaml`` → ``change_acceptance``, owned by the bank):

- ACCEPT when at least one check improves by at least ``min_gain`` with the whole
  interval above zero, and no check falls by more than ``max_regression``.
- REJECT when any check falls by more than ``max_regression``.
- NO EFFECT otherwise.

**Proof cases only.** A change chosen by looking at some cases must be proven on
others. The diff warns loudly if either run was not on the ``proof`` split.

**What persists becomes a vendor finding.** If the change targeted a lever and
failures with that lever's cause survive it, the bank has done what it can.

The change record is itself verifiable: ``evidence verify <change-dir>`` checks
both packs, confirms they are the ones recorded, and recomputes the comparison.
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

from evidence.derive import dump_json
from evidence.settings import Settings, changed_fields

# Which lever a setting belongs to — to tell whether a persisting cause was targeted.
SETTING_LEVER = {
    "context": "context", "retrieval": "search", "corpus": "search",
    "instructions": "instructions", "output_template": "template", "assistant": "model",
}


def _per_case(results: list[dict]) -> dict[str, dict[str, float]]:
    """check -> item -> share of exercised repeats that passed."""
    acc: dict[str, dict[str, list[bool]]] = defaultdict(lambda: defaultdict(list))
    for r in results:
        if r["applicable"]:
            acc[r["check"]][r["item_id"]].append(r["passed"])
    return {c: {i: sum(v) / len(v) for i, v in items.items()} for c, items in acc.items()}


def _interval(deltas: list[float]) -> tuple[float, float, float]:
    n = len(deltas)
    mean = sum(deltas) / n
    if n < 2:
        return mean, mean, mean
    sd = math.sqrt(sum((d - mean) ** 2 for d in deltas) / (n - 1))
    half = 1.96 * sd / math.sqrt(n)
    return mean, mean - half, mean + half


def _load(ev: Path) -> dict[str, Any]:
    return {
        "root": json.loads((ev / "CHECKSUMS.json").read_text())["root"],
        "run": json.loads((ev / "run_manifest.json").read_text()),
        "settings": Settings.model_validate(yaml.safe_load((ev / "settings.yaml").read_text())),
        "results": [json.loads(x) for x in (ev / "results.jsonl").read_text().splitlines() if x],
        "aggregate": json.loads((ev / "aggregate.json").read_text()),
        "diagnosis": json.loads((ev / "diagnosis.json").read_text()),
        "thresholds": yaml.safe_load((ev / "thresholds.yaml").read_text()) or {},
    }


def compare(before_dir: str | Path, after_dir: str | Path) -> dict[str, Any]:
    a, b = _load(Path(before_dir)), _load(Path(after_dir))
    rule = {"min_gain": 0.05, "max_regression": 0.02,
            **b["thresholds"].get("change_acceptance", {})}

    warnings = []
    if a["run"]["pack_items_sha256"] != b["run"]["pack_items_sha256"]:
        warnings.append("The two runs used different case packs; the comparison is not paired.")
    for label, x in (("before", a), ("after", b)):
        if x["run"].get("split") != "proof":
            warnings.append(f"The {label} run was not on PROOF cases (split: "
                            f"{x['run'].get('split') or 'all'}). A change must be proven on cases "
                            "that were not used to choose it.")
    if a["run"].get("simulated") or b["run"].get("simulated"):
        warnings.append("At least one run used the simulated assistant. This comparison tests the "
                        "engine; it is not evidence that the change works on a real assistant.")

    pa, pb = _per_case(a["results"]), _per_case(b["results"])
    checks = []
    for name in sorted(set(pa) | set(pb)):
        common = sorted(set(pa.get(name, {})) & set(pb.get(name, {})))
        if not common:
            checks.append({"check": name, "cases": 0, "status": "not_comparable"})
            continue
        deltas = [pb[name][i] - pa[name][i] for i in common]
        mean, lo, hi = _interval(deltas)
        rate_a = a["aggregate"]["checks"].get(name, {}).get("pass_rate")
        rate_b = b["aggregate"]["checks"].get(name, {}).get("pass_rate")
        improved = mean >= rule["min_gain"] and lo > 0
        regressed = mean <= -rule["max_regression"]
        checks.append({
            "check": name, "cases": len(common),
            "before": rate_a, "after": rate_b,
            "change": round(mean, 4), "interval": [round(lo, 4), round(hi, 4)],
            "helped": sum(1 for d in deltas if d > 0), "hurt": sum(1 for d in deltas if d < 0),
            "unchanged": sum(1 for d in deltas if d == 0),
            "status": "improved" if improved else "regressed" if regressed else "no_clear_change",
        })

    verdict = ("REJECT" if any(c["status"] == "regressed" for c in checks)
               else "ACCEPT" if any(c["status"] == "improved" for c in checks) else "NO EFFECT")

    changes = changed_fields(a["settings"], b["settings"])
    changed_levers = sorted({SETTING_LEVER.get(c["setting"].split(".")[0], "other")
                             for c in changes})

    def causes(x: dict) -> dict[str, dict]:
        return {c["cause"]: c for c in x["diagnosis"]["causes"]}

    ca, cb = causes(a), causes(b)
    cause_rows = []
    for cause in sorted(set(ca) | set(cb), key=lambda c: -(ca.get(c, {}).get("results", 0))):
        before = ca.get(cause, {}).get("results", 0)
        after = cb.get(cause, {}).get("results", 0)
        lever = (ca.get(cause) or cb.get(cause))["lever"]
        cause_rows.append({
            "cause": cause, "lever": lever, "before": before, "after": after,
            "targeted": lever in changed_levers,
            "persists_after_targeting": lever in changed_levers and after > 0,
            "new": before == 0 and after > 0,
        })

    return {
        "before": {"evidence": str(before_dir), "root": a["root"], "run_id": a["run"]["run_id"],
                   "settings": a["settings"].name, "split": a["run"].get("split")},
        "after": {"evidence": str(after_dir), "root": b["root"], "run_id": b["run"]["run_id"],
                  "settings": b["settings"].name, "split": b["run"].get("split")},
        "simulated": bool(a["run"].get("simulated") or b["run"].get("simulated")),
        "rule": rule,
        "settings_changed": changes,
        "levers_changed": changed_levers,
        "checks": checks,
        "verdict": verdict,
        "causes": cause_rows,
        "vendor_candidates": [c["cause"] for c in cause_rows if c["persists_after_targeting"]],
        "warnings": warnings,
    }


def _render(cmp: dict, out: Path) -> str:
    from evidence.report import _env

    rel = {k: os.path.relpath(Path(cmp[k]["evidence"]) / "reports" / "index.html", out)
           for k in ("before", "after")}
    return _env().get_template("change.html.j2").render(c=cmp, links=rel)


def write_change_record(before_dir: str | Path, after_dir: str | Path, out: str | Path) -> Path:
    from evidence.evidence_pack.writer import write_checksums

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    cmp = compare(before_dir, after_dir)
    (out / "comparison.json").write_bytes(dump_json(cmp))
    (out / "change.html").write_text(_render(cmp, out))
    write_checksums(out, attester=None, seal_key=os.environ.get("EVIDENCE_SEAL_KEY"))
    return out


def verify_change(root: str | Path):
    """Both packs verify, are the packs recorded, and the comparison recomputes."""
    from evidence.evidence_pack.verify import VerifyReport, _first_difference, verify

    root = Path(root)
    rep = VerifyReport(root=root)
    stored = json.loads((root / "comparison.json").read_text())
    for side in ("before", "after"):
        path = Path(stored[side]["evidence"])
        if not path.is_absolute() and not path.exists():
            path = root / path
        sub = verify(path)
        if not sub.ok:
            rep.errors.append(f"{side} pack does not verify: {sub.errors[0]}")
            continue
        root_now = json.loads((path / "CHECKSUMS.json").read_text())["root"]
        if root_now != stored[side]["root"]:
            rep.errors.append(f"{side} pack is not the one this change record was made from")
        else:
            rep.checked.append(f"{side} pack verifies and is the one recorded")
    if not rep.errors:
        fresh = compare(stored["before"]["evidence"], stored["after"]["evidence"])
        d = _first_difference(stored, fresh)
        if d:
            rep.errors.append(f"comparison.json: {d[0]} — stored {d[1]!r}, recomputed {d[2]!r}")
        else:
            rep.checked.append("comparison recomputed from both packs and matches")
            html = _render(fresh, root)
            if (root / "change.html").read_text() != html:
                rep.errors.append("change.html does not match the recomputed comparison")
    return rep
