# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Commands beyond run / pack / verify: diff (and, in later stages, guard and monitor)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def cmd_diff(a: argparse.Namespace) -> int:
    from evidence.diff import write_change_record

    before, after = Path(a.before), Path(a.after)
    out = Path(a.out or Path("changes") / f"{before.name}__to__{after.name}")
    write_change_record(before, after, out)
    c = json.loads((out / "comparison.json").read_text())
    for w in c["warnings"]:
        print(f"WARNING: {w}")
    print(f"{c['before']['settings']} -> {c['after']['settings']}: {c['verdict']}")
    for s in c["settings_changed"]:
        print(f"  changed {s['setting']}")
    for r in c["checks"]:
        if r["status"] == "not_comparable":
            continue
        print(f"  {r['check']:22} {r['before'] or 0:5.0%} -> {r['after'] or 0:5.0%}  "
              f"{r['change'] * 100:+4.0f} pts  [{r['interval'][0] * 100:+.0f}, "
              f"{r['interval'][1] * 100:+.0f}]  helped {r['helped']:2} hurt {r['hurt']:2}  "
              f"{r['status']}")
    for v in c["vendor_candidates"]:
        print(f"  persists after the bank changed its lever -> raise with vendor: {v}")
    print(f"Open: {out / 'change.html'}")
    a._audit = (str(out), {"verdict": c["verdict"], "before": c["before"]["root"],
                           "after": c["after"]["root"],
                           "settings_changed": [x["setting"] for x in c["settings_changed"]]})
    return 0


def cmd_guard(a: argparse.Namespace) -> int:
    from evidence.guard import (
        load_guard_config,
        load_referrals,
        referrals_from_pack,
        run_guard,
    )
    from evidence.settings import load_settings

    settings = load_settings(a.settings)
    cfg = load_guard_config(a.guard)
    if a.referrals:
        referrals = load_referrals(a.referrals)
    else:
        from evidence.packs import load_pack

        items = load_pack(a.pack).select(a.split, a.limit)
        referrals = referrals_from_pack(items, received_at=a.received_at)
        print(f"Pilot mode: {len(referrals)} referrals built from {a.pack} "
              f"(documents and rules-engine reason codes only; no answer key).")
    out = Path(a.out or Path("guard") / f"{settings.name}__{cfg.name}")
    run_guard(referrals, settings, cfg, out)
    m = json.loads((out / "monitoring.json").read_text())
    a._audit = (str(out), {"referrals": m["referrals"], "escalated": m["escalated"],
                           "first_attempt_pass_rate": m["first_attempt_pass_rate"]})
    return _print_monitoring(out)


def _print_monitoring(out: Path) -> int:
    m = json.loads((out / "monitoring.json").read_text())
    if m["simulated"]:
        print("SIMULATED ASSISTANT — these numbers test the guard, they are not evidence.")
    pct = lambda x: "—" if x is None else f"{x:.0%}"  # noqa: E731
    print(f"{m['referrals']} referrals")
    print(f"  first-attempt pass rate  {pct(m['first_attempt_pass_rate'])}   <- watch this")
    print(f"  after the guard          {pct(m['after_guard_pass_rate'])}")
    print(f"  escalated                {m['escalated']} ({pct(m['escalation_rate'])})")
    for c, n in m["failures_first_attempt"].items():
        still = m["failures_after_guard"].get(c, 0)
        print(f"    {c:24} failed first time {n:3}   still failing {still:3}")
    print(f"Open: {out / 'monitoring.html'}")
    return 0


def cmd_monitor(a: argparse.Namespace) -> int:
    from evidence.guard import write_monitoring

    write_monitoring(a.guard_dir)
    return _print_monitoring(Path(a.guard_dir))


def assistant_fingerprint(settings, version: str | None) -> dict:
    """What identifies the assistant being tested: model, endpoint, the vendor's version label."""
    a = settings.assistant
    if a.adapter == "scripted":
        model, endpoint = f"scripted/{a.profile or 'vendor-sim'}", "simulated"
    elif a.adapter == "callable":
        model, endpoint = a.model or a.callable, f"callable:{a.callable}"
    else:
        from evidence.adapters.nvidia_build import endpoint_for

        ep = endpoint_for(a.role)
        model, endpoint = a.model or ep.model_id, a.base_url or ep.base_url
    return {"model": model, "endpoint": endpoint, "version": version,
            "settings_sha256": settings.sha256()}


def cmd_watch(a: argparse.Namespace) -> int:
    """Re-run validation when the assistant changes, and diff against the last run."""
    from evidence.evidence_pack import write_evidence_pack
    from evidence.packs import load_pack
    from evidence.runner import run_pack
    from evidence.settings import load_settings

    settings = load_settings(a.settings)
    state_path = Path(a.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    fp = assistant_fingerprint(settings, a.version)
    last = state.get(settings.name)
    if last and last["fingerprint"] == fp:
        print(f"No change to {settings.name}: {fp['model']} {fp['version'] or ''}".rstrip())
        return 0
    why = "first run" if not last else "assistant changed: " + ", ".join(
        k for k in fp if fp[k] != last["fingerprint"].get(k))
    print(f"{settings.name}: {why} — running the validation pack")
    pack = load_pack(a.pack)
    tag = (a.version or fp["model"]).replace("/", "_").replace(":", "_")
    run_id = f"{settings.name}-{a.split or 'all'}-{tag}-{settings.sha256()[:8]}"
    run_dir, m = run_pack(pack, settings, a.runs, split=a.split, run_id=run_id)
    ev = write_evidence_pack(run_dir, pack, Path(a.evidence) / m.run_id)
    rc = 0
    if last and Path(last["evidence"]).exists():
        from evidence.diff import write_change_record

        out = write_change_record(last["evidence"], ev,
                                  Path("changes") / f"{Path(last['evidence']).name}__to__{ev.name}")
        c = json.loads((out / "comparison.json").read_text())
        print(f"Against the previous version: {c['verdict']}  ({out / 'change.html'})")
        for r in c["checks"]:
            if r["status"] == "regressed":
                print(f"  REGRESSED {r['check']}: {r['change'] * 100:+.0f} pts")
        rc = 1 if c["verdict"] == "REJECT" else 0
    a._audit = (str(ev), {"reason": why, "fingerprint": fp, "exit": rc})
    state[settings.name] = {"fingerprint": fp, "evidence": str(ev)}
    state_path.write_text(json.dumps(state, indent=2) + "\n")
    print(f"Evidence: {ev / 'reports' / 'index.html'}")
    return rc


def cmd_sign(a: argparse.Namespace) -> int:
    from evidence.signing import available, sign

    if not available():
        print("ssh-keygen not found; install OpenSSH to sign packs.")
        return 1
    sig = sign(a.pack_dir, a.key)
    print(f"Signed: {sig}")
    a._audit = (str(a.pack_dir), {"signature": str(sig)})
    return 0


def cmd_approve(a: argparse.Namespace) -> int:
    """A person approves a proven change. Refuses unless the change record verifies and was
    accepted — or the approver overrides with a written reason."""
    from evidence.audit import require_role
    from evidence.diff import verify_change

    who = require_role("approver", a.roles)
    rep = verify_change(a.change_dir)
    if not rep.ok:
        print(rep.render())
        print("Not approved: the change record does not verify.")
        return 1
    c = json.loads((Path(a.change_dir) / "comparison.json").read_text())
    if c["simulated"]:
        print("Not approved: the change was proven on the simulated assistant, which is never "
              "evidence.")
        return 1
    if c["verdict"] != "ACCEPT" and not a.override:
        print(f"Not approved: the change record says {c['verdict']}. Pass --override "
              f"'<reason>' to approve anyway; the reason goes in the audit log.")
        return 1
    print(f"Approved by {who}: {c['before']['settings']} -> {c['after']['settings']} "
          f"({c['verdict']}{', overridden' if a.override else ''})")
    a._audit = (str(a.change_dir), {"verdict": c["verdict"], "override": a.override,
                                    "settings_changed": [x["setting"]
                                                         for x in c["settings_changed"]],
                                    "after_root": c["after"]["root"]})
    return 0


def cmd_audit(a: argparse.Namespace) -> int:
    from evidence.audit import _lines, log_path, verify_log

    path = Path(a.log) if a.log else log_path()
    for e in _lines(path)[-a.tail:]:
        print(f"{e['seq']:4}  {e['at']}  {e['actor']:12} {e['action']:8} {e['subject']}")
    problems = verify_log(path)
    for p in problems:
        print(f"BROKEN  {p}")
    print("audit log intact" if not problems else f"audit log BROKEN ({len(problems)} problem(s))")
    return 0 if not problems else 1


def cmd_annotate(a: argparse.Namespace) -> int:
    """Run the agent slots switched on in the settings file over a finished pack."""
    import yaml

    from evidence.slots import annotate

    src = Path(a.settings) if a.settings else Path(a.pack_dir) / "settings.yaml"
    agents = (yaml.safe_load(src.read_text()) or {}).get("agents") or {}
    if not any(agents.values()):
        print(f"No agent slots are switched on in {src}. Nothing to do; the defaults already "
              f"ran.")
        return 0
    notes = annotate(a.pack_dir, agents)
    shown = sum(n.status == "shown" for n in notes)
    print(f"{len(notes)} agent note(s): {shown} shown, {len(notes) - shown} rejected "
          f"(a note may not contain figures).")
    a._audit = (str(a.pack_dir), {"agents": {k: v for k, v in agents.items() if v},
                                  "notes": len(notes), "shown": shown})
    return 0


def register(sub: argparse._SubParsersAction) -> None:
    d = sub.add_parser("diff", help="prove a change: compare two evidence packs case by case")
    d.add_argument("before", help="evidence pack for the current settings")
    d.add_argument("after", help="evidence pack for the proposed settings")
    d.add_argument("--out", help="where to write the change record (default changes/…)")
    d.set_defaults(fn=cmd_diff)

    g = sub.add_parser("guard", help="check live briefings before an underwriter sees them")
    g.add_argument("--settings", required=True, help="the assistant's settings file")
    g.add_argument("--guard", default="settings/guard.yaml", help="the bank's guard config")
    g.add_argument("--referrals", help="JSON lines of live referrals (contracts/referral.py)")
    g.add_argument("--pack", default="packs/underwriter-sample",
                   help="pilot mode: build referrals from a case pack when no feed exists")
    g.add_argument("--split", choices=["tune", "proof"])
    g.add_argument("--limit", type=int)
    g.add_argument("--received-at", help="date stamped on pilot referrals (ISO 8601)")
    g.add_argument("--out")
    g.set_defaults(fn=cmd_guard)

    w = sub.add_parser("watch", help="re-run validation when the assistant or its version "
                                     "changes; exit 1 if the new version is worse")
    w.add_argument("--settings", required=True)
    w.add_argument("--version", help="the vendor's version label, if the model id does not change")
    w.add_argument("--state", default="runs/watch_state.json")
    w.add_argument("--pack", default="packs/underwriter-sample")
    w.add_argument("--split", default="proof", choices=["tune", "proof"])
    w.add_argument("--runs", default="runs")
    w.add_argument("--evidence", default="evidence")
    w.set_defaults(fn=cmd_watch)

    sg = sub.add_parser("sign", help="sign an evidence pack with an SSH key (public-key)")
    sg.add_argument("pack_dir")
    sg.add_argument("--key", required=True, help="private key, e.g. ~/.ssh/id_ed25519")
    sg.set_defaults(fn=cmd_sign)

    ap = sub.add_parser("approve", help="approve a proven change (needs the approver role)")
    ap.add_argument("change_dir")
    ap.add_argument("--override", help="approve a change that was not ACCEPTED; give the reason")
    ap.add_argument("--roles", default="settings/roles.yaml")
    ap.set_defaults(fn=cmd_approve)

    au = sub.add_parser("audit", help="show the audit log and check its hash chain")
    au.add_argument("--log")
    au.add_argument("--tail", type=int, default=20)
    au.set_defaults(fn=cmd_audit)

    an = sub.add_parser("annotate", help="run the optional agent slots over an evidence pack")
    an.add_argument("pack_dir")
    an.add_argument("--settings", help="settings file whose `agents:` to use (default: the "
                                       "pack's own)")
    an.set_defaults(fn=cmd_annotate)

    m = sub.add_parser("monitor", help="rebuild the monitoring report from a guard log")
    m.add_argument("guard_dir")
    m.set_defaults(fn=cmd_monitor)
