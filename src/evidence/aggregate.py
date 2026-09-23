# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Adding the results up — by check, by split, by difficulty, by variant, by obligation.

Pure and deterministic: the same results always give the same aggregate, to the
byte. That is what lets the verifier recompute every number and name the one
that no longer adds up.

A result marked not applicable (``applicable: false``) is counted as "not
exercised", never as a pass. Pass rates are over exercised results only.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from evidence.contracts.item import BenchmarkItem

IMPLEMENTED_NOTE = "not implemented in this engine version"

# Obligation grid entries that are parts of the evidence pack rather than checks.
PROVIDED_BY_PACK = {
    "non_claims": "provided by this pack: 'What this does not test' on the decision page",
    "coverage_grid": "provided by this pack: this regulation map",
}


def _rate(p: int, f: int) -> float | None:
    return round(p / (p + f), 4) if p + f else None


def _tally(rows: list[dict]) -> dict[str, Any]:
    p = sum(1 for r in rows if r["applicable"] and r["passed"])
    f = sum(1 for r in rows if r["applicable"] and not r["passed"])
    return {"passed": p, "failed": f, "not_exercised": sum(1 for r in rows if not r["applicable"]),
            "pass_rate": _rate(p, f)}


def needs_audit_queue(results: list[dict]) -> list[dict]:
    """Every similarity match, weakest first: wording-anchored before figure-anchored,
    then by overlap. The top of this list is where a reviewer's time goes."""
    queue = []
    for r in results:
        for e in r.get("evidence", []):
            if e.get("method") == "similarity":
                queue.append({
                    "result_id": r["result_id"], "item_id": r["item_id"], "repeat": r["repeat"],
                    "check": r["check"], "ref": e["ref"], "form": e["form"],
                    "sentence": e["sentence"], "overlap": e["overlap"],
                    "anchor": e.get("anchor", "wording"),
                })
    queue.sort(key=lambda q: (q["anchor"] != "wording", q["overlap"], q["item_id"], q["repeat"]))
    return queue


def aggregate(
    results: list[dict],
    items: dict[str, BenchmarkItem],
    run: dict,
    obligations: dict,
) -> dict[str, Any]:
    by_check: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_check[r["check"]].append(r)

    checks: dict[str, Any] = {}
    for name in sorted(by_check):
        rows = by_check[name]
        per_item: dict[str, list[bool]] = defaultdict(list)
        for r in rows:
            if r["applicable"]:
                per_item[r["item_id"]].append(r["passed"])
        dims: dict[str, dict[str, Any]] = {}
        for dim in ("split", "difficulty", "variant"):
            groups: dict[str, list[dict]] = defaultdict(list)
            for r in rows:
                groups[items[r["item_id"]].tags.get(dim, "-")].append(r)
            dims[f"by_{dim}"] = {k: _tally(v) for k, v in sorted(groups.items())}
        checks[name] = {
            **_tally(rows),
            "needs_audit": sum(1 for r in rows if r["needs_audit"]),
            "items": {
                "n": len(per_item),
                "all_repeats_pass": sum(1 for v in per_item.values() if all(v)),
                "any_repeat_fails": sum(1 for v in per_item.values() if not all(v)),
            },
            "repeat_agreement": _rate(
                sum(1 for v in per_item.values() if len(set(v)) == 1),
                sum(1 for v in per_item.values() if len(set(v)) > 1),
            ),
            **dims,
            "failed_result_ids": sorted(r["result_id"] for r in rows
                                        if r["applicable"] and not r["passed"]),
        }

    by_call: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        by_call[r["transcript_sha256"]].append(r)
    clean = sum(1 for rs in by_call.values() if all(r["passed"] for r in rs if r["applicable"]))

    ob_rows = []
    for ob in obligations.get("obligations", []):
        row = {"id": ob["id"], "title": ob["title"], "level": ob["level"]}
        if "reason" in ob:
            row["reason"] = ob["reason"]
        row["checks"] = [
            {"name": c, "pass_rate": checks[c]["pass_rate"], "failed": checks[c]["failed"]}
            if c in checks
            else {"name": c, "pass_rate": None, "provided": PROVIDED_BY_PACK[c]}
            if c in PROVIDED_BY_PACK
            else {"name": c, "pass_rate": None, "note": IMPLEMENTED_NOTE}
            for c in ob.get("grid", [])
        ]
        ob_rows.append(row)

    return {
        "run_id": run["run_id"],
        "settings_name": run["settings_name"],
        "simulated": run.get("simulated", False),
        "split": run.get("split"),
        "repeats": run["repeats"],
        "calls": len(by_call),
        "items": len({r["item_id"] for r in results}),
        "overall": {"calls": len(by_call), "calls_all_checks_pass": clean,
                    "pass_rate": _rate(clean, len(by_call) - clean)},
        "checks": checks,
        "needs_audit": needs_audit_queue(results),
        "obligations": ob_rows,
    }
