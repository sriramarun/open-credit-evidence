# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""The 'one successful Nemotron call' from PLAN.md, for all three models.

    export NVIDIA_API_KEY=...        # or put it in .env
    .venv/bin/python scripts/smoke_nvidia.py

Makes one call each to the assistant, the judge and the embedder, on the first
case in the sample pack, and prints what came back with the pinned model id,
prompt hash, latency and token counts — the fields the run manifest records.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from evidence.adapters.nvidia_build import MODELS, chat, embed
from evidence.contracts.item import BenchmarkItem

PACK = Path(__file__).resolve().parents[1] / "packs" / "underwriter-sample"


def main() -> int:
    items = [BenchmarkItem.model_validate_json(line) for line in (PACK / "items.jsonl").open()]
    item = items[0]
    case_id = item.item_id.split(":")[2]
    print("models:", json.dumps(MODELS, indent=2))

    # 1. embed — index the two documents as passages, then search with a query
    docs = [c.content for c in item.context]
    vecs = embed(docs, input_type="passage")
    q = embed(["what is the applicant's debt-to-income ratio"], input_type="query")[0]
    dots = [sum(a * b for a, b in zip(v, q, strict=True)) for v in vecs]
    best = max(range(len(docs)), key=lambda i: dots[i])
    print(f"\n[embed] {len(vecs)} passages x {len(vecs[0])} dims; "
          f"query matched '{item.context[best].renderer}' (score {dots[best]:.3f})")

    # 2. assistant — the underwriter briefing on the real case
    r = chat("assistant", system=item.prompt, user="\n\n".join(docs), max_tokens=600)
    print(f"\n[assistant] {r.model_id}  prompt={r.prompt_version}  "
          f"{r.latency_ms} ms  in={r.tokens_in} out={r.tokens_out}")
    print("-" * 70)
    print(r.text.strip()[:1200])
    print("-" * 70)

    # 3. judge — grade that briefing on one rubric line, thinking on
    rubric = (
        "You are grading an underwriter briefing. Answer with a JSON object "
        '{"intelligible": 0-2, "actionable": 0-2, "reason": "..."}. '
        "intelligible: could an underwriter understand it without re-reading the file. "
        "actionable: can they tell what would need to change for a different outcome."
    )
    j = chat("judge", system=rubric, user=f"CASE {case_id}\n\nBRIEFING:\n{r.text}", max_tokens=800)
    print(f"\n[judge] {j.model_id}  prompt={j.prompt_version}  "
          f"{j.latency_ms} ms  in={j.tokens_in} out={j.tokens_out}")
    print("-" * 70)
    print(j.text.strip()[:800])
    print("-" * 70)

    # 4. the omission check on what the assistant actually wrote
    from evidence.checks import run_checks

    (chk,) = run_checks(["material_omission"], output=r.text, item=item)
    print(f"\n[material_omission] {'PASS' if chk.passed else 'FAIL'}  "
          f"score {chk.score:.2f}  needs_audit={chk.needs_audit}\n  {chk.detail}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
