# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
# ruff: noqa: E501 — this script is mostly HTML strings
"""Build a local landing page over every evidence pack, change record and guard report.

    .venv/bin/python scripts/local_site.py
    .venv/bin/python -m http.server 8817 --directory site

Writes ``site/index.html`` and links ``site/evidence``, ``site/changes`` and
``site/guard`` to the real folders, so the server exposes nothing else from the
repository (no .env, no answer key).
"""

from __future__ import annotations

import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def _j(p: Path) -> dict:
    return json.loads(p.read_text())


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x:.0%}"


def _verified(folder: Path) -> str:
    from evidence.evidence_pack import verify

    if (folder / "comparison.json").exists():
        from evidence.diff import verify_change

        return "verified" if verify_change(folder).ok else "REJECTED"
    if (folder / "guard_log.jsonl").exists():
        from evidence.guard import verify_guard

        return "verified" if verify_guard(folder).ok else "REJECTED"
    return "verified" if verify(folder).ok else "REJECTED"


def packs() -> list[dict]:
    rows = []
    for d in sorted((ROOT / "evidence").glob("*/decision.json")):
        folder = d.parent
        dec, agg = _j(d), _j(folder / "aggregate.json")
        rows.append({
            "name": folder.name, "href": f"evidence/{folder.name}/reports/index.html",
            "real": not dec["simulated"], "verdict": dec["verdict"],
            "would_be": dec["would_be"], "first": dec["first_attempt_pass_rate"],
            "calls": agg["calls"], "items": agg["items"], "check": _verified(folder),
        })
    return rows


def changes() -> list[dict]:
    rows = []
    for c in sorted((ROOT / "changes").glob("*/comparison.json")):
        cmp = _j(c)
        rows.append({
            "href": f"changes/{c.parent.name}/change.html",
            "label": f"{cmp['before']['settings']} → {cmp['after']['settings']}",
            "verdict": cmp["verdict"], "simulated": cmp["simulated"],
            "changed": ", ".join(s["setting"] for s in cmp["settings_changed"]) or "nothing",
            "check": _verified(c.parent),
        })
    return rows


def guards() -> list[dict]:
    rows = []
    for m in sorted((ROOT / "guard").glob("*/monitoring.json")):
        mon = _j(m)
        rows.append({
            "href": f"guard/{m.parent.name}/monitoring.html", "name": m.parent.name,
            "simulated": mon["simulated"], "n": mon["referrals"],
            "first": mon["first_attempt_pass_rate"], "after": mon["after_guard_pass_rate"],
            "escalated": mon["escalated"], "check": _verified(m.parent),
        })
    return rows


CSS = """
:root{--ink:#1c1f24;--muted:#5d6570;--line:#dfe3e8;--bg:#fbfbfa;--card:#fff;--link:#1f5fbf;
--go:#1d7a46;--go-bg:#e6f4ec;--no:#b3261e;--no-bg:#fbe9e7;--cond:#8a5a00;--cond-bg:#fdf3dc;
--sim:#5b3fa6;--sim-bg:#efeafb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
main{max-width:1040px;margin:0 auto;padding:28px 24px 48px}h1{font-size:26px;margin:0 0 4px}
h2{font-size:18px;margin:30px 0 10px}p{margin:6px 0}.muted{color:var(--muted)}.small{font-size:13px}
a{color:var(--link)}.scroll{overflow-x:auto}
table{width:100%;border-collapse:collapse;background:var(--card);border:1px solid var(--line);font-size:14px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#f3f4f6;font-size:13px;color:var(--muted)}td.num{text-align:right;font-variant-numeric:tabular-nums}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap}
.real{background:#e8f0fc;color:#1f4f99}.sim{background:var(--sim-bg);color:var(--sim)}
.GO,.ACCEPT,.verified{background:var(--go-bg);color:var(--go)}
.NO-GO,.REJECT,.REJECTED{background:var(--no-bg);color:var(--no)}
.cond{background:var(--cond-bg);color:var(--cond)}
ol li{margin:4px 0}code{font:12.5px ui-monospace,Menlo,Consolas,monospace;background:#f1f3f5;padding:1px 4px;border-radius:4px}
"""


def pill(text: str, cls: str | None = None) -> str:
    cls = cls or {"GO": "GO", "NO-GO": "NO-GO", "ACCEPT": "ACCEPT", "REJECT": "REJECT",
                  "verified": "verified", "REJECTED": "REJECTED"}.get(text, "cond")
    return f'<span class="pill {cls}">{html.escape(text)}</span>'


def build() -> Path:
    SITE.mkdir(exist_ok=True)
    for name in ("evidence", "changes", "guard"):
        link = SITE / name
        if link.is_symlink() or link.exists():
            link.unlink()
        if (ROOT / name).exists():
            link.symlink_to(ROOT / name, target_is_directory=True)

    p, c, g = packs(), changes(), guards()
    out = [f"<!doctype html><html lang=en><head><meta charset=utf-8>"
           f"<meta name=viewport content='width=device-width,initial-scale=1'>"
           f"<title>Credit Evidence Engine — local</title><style>{CSS}</style></head><body><main>",
           "<h1>Credit Evidence Engine</h1>",
           "<p class=muted>Everything generated on this machine. <span class='pill real'>real</span> "
           "runs used the assistant named in <code>.env</code>; <span class='pill sim'>simulated</span> "
           "runs used the engine's test double and are never evidence.</p>",
           "<h2>Where to start</h2><ol>"]
    real = [r for r in p if r["real"]]
    if real:
        out.append(f"<li>The real assistant's one-page decision: <a href='{real[0]['href'].replace('index.html', 'decision.html')}'>{html.escape(real[0]['name'])}</a></li>")
        out.append(f"<li>What went wrong, with examples: <a href='{real[0]['href'].replace('index.html', 'failures.html')}'>failure cards</a> · what to change: <a href='{real[0]['href'].replace('index.html', 'recommendations.html')}'>recommendations</a></li>")
    real_c = [x for x in c if not x["simulated"]]
    if real_c:
        out.append(f"<li>Proof that a recommended change works: <a href='{real_c[0]['href']}'>{html.escape(real_c[0]['label'])}</a></li>")
    if g:
        out.append(f"<li>The production guard's monitoring: <a href='{g[0]['href']}'>{html.escape(g[0]['name'])}</a></li>")
    out.append("</ol>")

    out.append("<h2>Evidence packs</h2><div class=scroll><table><tr><th>Pack</th><th>Assistant</th>"
               "<th>Verdict</th><th class=num>First-attempt pass</th><th class=num>Calls</th>"
               "<th>Integrity</th></tr>")
    for r in sorted(p, key=lambda r: (not r["real"], r["name"])):
        verdict = pill(r["verdict"]) if r["real"] else (
            pill("not evidence", "sim") + f" <span class=small>would be {html.escape(r['would_be'])}</span>")
        out.append(f"<tr><td><a href='{r['href']}'>{html.escape(r['name'])}</a></td>"
                   f"<td>{pill('real', 'real') if r['real'] else pill('simulated', 'sim')}</td>"
                   f"<td>{verdict}</td><td class=num>{_pct(r['first'])}</td>"
                   f"<td class=num>{r['calls']}</td><td>{pill(r['check'])}</td></tr>")
    out.append("</table></div>")

    out.append("<h2>Change records</h2><div class=scroll><table><tr><th>Change</th><th>Assistant</th>"
               "<th>Setting changed</th><th>Verdict</th><th>Integrity</th></tr>")
    for x in sorted(c, key=lambda x: x["simulated"]):
        out.append(f"<tr><td><a href='{x['href']}'>{html.escape(x['label'])}</a></td>"
                   f"<td>{pill('simulated', 'sim') if x['simulated'] else pill('real', 'real')}</td>"
                   f"<td><code>{html.escape(x['changed'])}</code></td><td>{pill(x['verdict'])}</td>"
                   f"<td>{pill(x['check'])}</td></tr>")
    out.append("</table></div>")

    out.append("<h2>Production guard</h2><div class=scroll><table><tr><th>Guard log</th><th>Assistant</th>"
               "<th class=num>Referrals</th><th class=num>First attempt</th><th class=num>After guard</th>"
               "<th class=num>Escalated</th><th>Integrity</th></tr>")
    for x in g:
        out.append(f"<tr><td><a href='{x['href']}'>{html.escape(x['name'])}</a></td>"
                   f"<td>{pill('simulated', 'sim') if x['simulated'] else pill('real', 'real')}</td>"
                   f"<td class=num>{x['n']}</td><td class=num>{_pct(x['first'])}</td>"
                   f"<td class=num>{_pct(x['after'])}</td><td class=num>{x['escalated']}</td>"
                   f"<td>{pill(x['check'])}</td></tr>")
    out.append("</table></div>")
    out.append("<p class='small muted'>Integrity is <code>python -m evidence verify</code>, re-run "
               "when this page was built: every file checked, every number recomputed.</p>"
               "</main></body></html>")
    (SITE / "index.html").write_text("\n".join(out))
    return SITE / "index.html"


if __name__ == "__main__":
    print(build())
