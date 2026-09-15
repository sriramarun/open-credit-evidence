# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
"""Generate notebooks/01_models_smoke.ipynb. Edit this file, never the .ipynb.

    .venv/bin/python notebooks/build_models_smoke.py
    .venv/bin/jupyter nbconvert --to notebook --execute --inplace \
        --ExecutePreprocessor.kernel_name=credit-evidence \
        --ExecutePreprocessor.timeout=900 notebooks/01_models_smoke.ipynb
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

OUT = Path(__file__).with_name("01_models_smoke.ipynb")

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {
    "name": "credit-evidence",
    "display_name": "credit-evidence (.venv)",
    "language": "python",
}
cells = nb.cells
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))  # noqa: E731
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))  # noqa: E731

md("""
# The three models, on one real case

One referred loan application from the sample pack, run through everything we
call on NVIDIA Build:

| Role | Model | Why |
|---|---|---|
| Retriever | `nvidia/nemotron-3-embed-1b` | Finds which parts of the case file to read |
| Assistant | `nvidia/nemotron-3.5-lightning-30b-a3b` | Writes the briefing from retrieved text |
| Judge | `nvidia/nemotron-3-ultra-550b-a55b` | Grades readability — never completeness |

Then our own check — no model involved — asks the only question a validator cares
about: **did the briefing state the facts the decision turned on?**

Nemotron 3 Super is not here. Its free endpoint is deprecated on 2 October 2026,
five days before the final.
""")

code("""
import json
import re
import time
from pathlib import Path

from dotenv import load_dotenv

from evidence.adapters.nvidia_build import MODELS, chat
from evidence.adapters.rag import as_prompt, retrieve
from evidence.checks import run_checks
from evidence.contracts.item import BenchmarkItem

load_dotenv()
PACK = Path("../packs/underwriter-sample")
print(json.dumps(MODELS, indent=2))
""")

md("""
## 1. The case

Generated, not real. A hidden repayment-capacity tier drove the numbers; the tier was
dropped before the file was written. The assistant sees three documents: the application,
the bureau report, and an extract of the lending policy. The policy is where the 40%
limit lives — the assistant is not expected to know it from nowhere.
""")

code("""
items = [BenchmarkItem.model_validate_json(line) for line in (PACK / "items.jsonl").open()]
item = next(i for i in items if "APP000044" in i.item_id)
for doc in item.context:
    print(f"── {doc.renderer} ──")
    print(doc.content)
""")

md("""
## 2. What the marking key says — computed before any model ran

This is the sealed half of the item. The assistant never sees it.
""")

code("""
g = item.grading
print("outcome        :", g.disposition)
print("drivers        :", [g.driver_labels[r] for r in g.driver_refs])
print("must surface   :", [g.omission_labels[r] for r in g.omission_refs])
print("decoys (0 wt)  :", g.decoy_refs)
print("would flip it  :", [f.model_dump() for f in g.flip_refs])
""")

md("""
## 3. Retrieval — the assistant selects what to read

Each document is split on its section headings, embedded as `passage`, and the
question is embedded as `query`. Only the top four sections go to the assistant.
This is the deployment shape, and it introduces a failure mode worth recording: if
the section holding the ratio is never retrieved, the assistant cannot state it.
""")

code("""
t0 = time.perf_counter()
retrieved = retrieve(item.prompt, item.context, k=4)
print(f"retrieval took {time.perf_counter()-t0:.1f}s\\n")
for r in retrieved:
    print(f"{r.score:.3f}  {r.chunk_id}")
print("\\n── what the assistant is handed ──")
print(as_prompt(retrieved))
""")

md("""
## 4. The assistant writes the briefing

Nemotron 3.5 Lightning, temperature 0, seed pinned. It gets the retrieved sections
only. Every field returned here is what the run manifest records.
""")

code("""
a = chat("assistant", system=item.prompt, user=as_prompt(retrieved), max_tokens=700)
print(f"{a.model_id}  prompt={a.prompt_version}  {a.latency_ms/1000:.0f}s  "
      f"in={a.tokens_in} out={a.tokens_out}\\n")
print(a.text.strip())
""")

md("""
## 5. The judge grades readability

Nemotron 3 Ultra with thinking on. A different model from the one under test, and
larger — a judge should not be worse than the thing it grades. It is asked two
things a formula cannot check: could an underwriter understand this, and can they
tell what would need to change. **It is not asked about completeness.**
""")

code("""
RUBRIC = (
    "You are grading an underwriter briefing for readability only. Answer with a JSON "
    'object {"intelligible": 0-2, "actionable": 0-2, "reason": "..."}. '
    "intelligible: could an underwriter understand it without re-reading the file. "
    "actionable: can they tell what would need to change for a different outcome. "
    "Do not grade whether the briefing is complete or correct; that is checked elsewhere."
)
j = chat("judge", system=RUBRIC, user=f"BRIEFING:\\n{a.text}", max_tokens=600)
print(f"{j.model_id}  prompt={j.prompt_version}  {j.latency_ms/1000:.0f}s\\n")
print(j.text.strip())
""")

md("""
## 6. The check — no model involved

`material_omission` opens the marking key and looks for each required fact in the
briefing. Exact match first, then a similarity match that is flagged for audit, then
missing. It passes only at full marks — a briefing that surfaces two of three material
facts still misleads the underwriter.
""")

code("""
(chk,) = run_checks(["material_omission"], output=a.text, item=item)
print(f"material_omission → {'PASS' if chk.passed else 'FAIL'}   score {chk.score:.2f}   "
      f"needs_audit={chk.needs_audit}")
print(chk.detail, "\\n")
for e in chk.evidence:
    mark = "found  " if e["matched"] else "MISSING"
    via = f" via {e['method']}" if e.get("method") else ""
    print(f"  [{mark}] {g.omission_labels[e['ref']]}{via}")
""")

md("""
## 7. Was it retrieval or the model?

Three facts, one from each document. For each: is it in the file, was it retrieved,
is it in the briefing. The transcript records the retrieved chunks so this question
can always be answered after the fact.
""")

code(r"""
retrieved_text = " ".join(r.text for r in retrieved)
file_text = " ".join(d.content for d in item.context)
probes = {"40% limit (policy)": "40%", "instalment £314 (application)": "£314",
          "bureau score 652 (bureau report)": "652"}
print(f"{'fact':36} {'in file':>8} {'retrieved':>10} {'in briefing':>12}")
for label, needle in probes.items():
    print(f"{label:36} {str(needle in file_text):>8} {str(needle in retrieved_text):>10} "
          f"{str(needle in a.text):>12}")

print("\nNumbers the briefing states that appear nowhere in the case file:")
num = r"\d+(?:,\d{3})*(?:\.\d+)?"
file_nums = set(re.findall(num, file_text))
for n in sorted(set(re.findall(num, a.text)) - file_nums, key=lambda x: float(x.replace(",", ""))):
    print(f"  {n}")
""")

md("""
## What this shows

- **Three models, one endpoint, everything pinned.** Model id, prompt hash, parameters,
  latency and tokens recorded per call — the run manifest is built from these.
- **The judge and the check answer different questions.** The judge says whether the
  briefing reads well. The check says whether it told the underwriter what mattered.
- **RAG failed, and the framework saw it.** Retrieval ranked the policy sections above the
  data — the question reads like a policy question — so the assistant was handed rules and
  no numbers. It wrote a confident briefing anyway, with a ratio and a file-age claim that
  appear nowhere in the case. The judge gave it full marks. The omission check passed,
  because the breach *was* stated. Section 7 is what catches it: the numbers it used are
  not in the file. That is `numeric_fidelity`, the next check to port.
- **Why this is the point.** A briefing can be readable, complete on the facts we asked
  for, and still fabricated. No single check is enough; the pack runs all of them, and the
  transcript records what was retrieved so the failure can be attributed.
- **Retrieval fix for Week 2:** retrieve per document rather than across all chunks, so
  every source contributes, and query with the case fields rather than the task prompt.
- **Latency** was 8–10 s per call today against 100–150 s yesterday — the free endpoint
  varies. The runner stays resumable regardless.
""")

nb.metadata["language_info"] = {"name": "python"}
OUT.write_text(nbf.writes(nb))
print(f"wrote {OUT}")
