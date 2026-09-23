# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The ``evidence`` command.

    evidence run    --settings settings/baseline.yaml --split proof
    evidence verify evidence/baseline-proof-…
    evidence pack   runs/baseline-proof-…            # rebuild a pack from a finished run

``run`` puts every case to the assistant, checks every answer, and writes an
evidence pack (machine record plus readable views) that ``verify`` can re-check
from scratch.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_PACK = "packs/underwriter-sample"


def _summary(evidence_dir: Path) -> str:
    agg = json.loads((evidence_dir / "aggregate.json").read_text())
    lines = []
    if agg.get("simulated"):
        lines.append("SIMULATED ASSISTANT — these numbers test the engine, they are not evidence.")
    lines.append(f"{agg['run_id']}: {agg['calls']} calls over {agg['items']} items")
    for name, c in agg["checks"].items():
        rate = "  n/a" if c["pass_rate"] is None else f"{c['pass_rate']:.0%}".rjust(5)
        extra = f"  ({c['not_exercised']} not exercised)" if c["not_exercised"] else ""
        lines.append(f"  {name:22} {rate}   pass {c['passed']:3}  fail {c['failed']:3}{extra}")
    decision = evidence_dir / "decision.json"
    if decision.exists():
        lines.append(f"Decision: {json.loads(decision.read_text())['verdict']}")
    index = evidence_dir / "reports" / "index.html"
    if index.exists():
        lines.append(f"Open: {index}")
    return "\n".join(lines)


def cmd_run(a: argparse.Namespace) -> int:
    from evidence.evidence_pack import verify, write_evidence_pack
    from evidence.packs import load_pack
    from evidence.runner import run_pack
    from evidence.settings import load_settings

    pack = load_pack(a.pack)
    settings = load_settings(a.settings)
    if settings.simulated:
        print("NOTE: scripted assistant. Results exercise the engine and are never evidence.",
              file=sys.stderr)
    run_dir, manifest = run_pack(
        pack, settings, a.runs, split=a.split, repeats=a.repeats, limit=a.limit, rpm=a.rpm,
        run_id=a.run_id,
        progress=(lambda s: print(f"  {s}", file=sys.stderr)) if a.verbose else None,
    )
    if manifest.calls_done < manifest.calls_planned:
        print(f"WARNING: {manifest.calls_planned - manifest.calls_done} call(s) failed; "
              f"see {run_dir / 'errors.jsonl'}. Re-run the same command to resume.",
              file=sys.stderr)
    out = Path(a.evidence_out or Path(a.evidence) / manifest.run_id)
    write_evidence_pack(run_dir, pack, out, thresholds=a.thresholds, attester=a.attester)
    rep = verify(out)
    print(_summary(out))
    print(rep.render().splitlines()[-1])
    a._audit = (str(out), {"run_id": manifest.run_id, "settings": settings.name,
                           "settings_sha256": settings.sha256(), "split": a.split,
                           "calls": manifest.calls_done, "simulated": settings.simulated,
                           "root": _root(out), "verified": rep.ok})
    return 0 if rep.ok else 1


def cmd_pack(a: argparse.Namespace) -> int:
    from evidence.evidence_pack import write_evidence_pack
    from evidence.packs import load_pack

    run_dir = Path(a.run_dir)
    out = Path(a.out or Path(a.evidence) / run_dir.name)
    write_evidence_pack(run_dir, load_pack(a.pack), out, thresholds=a.thresholds,
                        attester=a.attester)
    print(_summary(out))
    a._audit = (str(out), {"from_run": str(run_dir), "root": _root(out)})
    return 0


def cmd_verify(a: argparse.Namespace) -> int:
    from evidence.evidence_pack import verify

    if (Path(a.evidence_dir) / "comparison.json").exists():
        from evidence.diff import verify_change

        rep = verify_change(a.evidence_dir)
    elif (Path(a.evidence_dir) / "guard_log.jsonl").exists():
        from evidence.guard import verify_guard

        rep = verify_guard(a.evidence_dir)
    else:
        rep = verify(a.evidence_dir, allowed_signers=a.allowed_signers)
    print(rep.render())
    return 0 if rep.ok else 1


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="evidence", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="run a case pack against the assistant and write evidence")
    r.add_argument("--settings", required=True)
    r.add_argument("--pack", default=DEFAULT_PACK)
    r.add_argument("--split", choices=["tune", "proof"])
    r.add_argument("--repeats", type=int)
    r.add_argument("--limit", type=int, help="first N items only (smoke runs)")
    r.add_argument("--rpm", type=float, help="max calls per minute (default 40; 0 = no limit)")
    r.add_argument("--run-id")
    r.add_argument("--runs", default="runs", help="where raw runs are kept")
    r.add_argument("--evidence", default="evidence", help="where evidence packs are written")
    r.add_argument("--evidence-out", help="exact folder for this evidence pack")
    r.add_argument("--thresholds", help="the bank's thresholds.yaml (default: engine defaults)")
    r.add_argument("--attester", help="name of the person who stands behind the pack")
    r.add_argument("-v", "--verbose", action="store_true")
    r.set_defaults(fn=cmd_run)

    k = sub.add_parser("pack", help="(re)write the evidence pack for a finished run")
    k.add_argument("run_dir")
    k.add_argument("--pack", default=DEFAULT_PACK)
    k.add_argument("--evidence", default="evidence")
    k.add_argument("--out")
    k.add_argument("--thresholds")
    k.add_argument("--attester")
    k.set_defaults(fn=cmd_pack)

    v = sub.add_parser("verify", help="re-check an evidence pack or change record from scratch")
    v.add_argument("evidence_dir")
    v.add_argument("--allowed-signers", help="OpenSSH allowed_signers file to check a signature")
    v.set_defaults(fn=cmd_verify)

    for extra in ("evidence.cli_more",):
        try:
            __import__(extra, fromlist=["register"]).register(sub)
        except ModuleNotFoundError as exc:
            if exc.name != extra:
                raise
    return p


def _root(path: Path) -> str | None:
    ck = Path(path) / "CHECKSUMS.json"
    return json.loads(ck.read_text())["root"] if ck.exists() else None


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    a._audit = None
    rc = a.fn(a)
    if a._audit:  # commands that produce or approve something leave a line in the audit log
        from evidence.audit import record

        subject, details = a._audit
        record(a.cmd, subject, {**details, "exit": rc})
    return rc


if __name__ == "__main__":
    sys.exit(main())
