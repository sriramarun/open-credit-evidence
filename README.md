# Credit Evidence Engine

Tests AI assistants that compile a case file for a human who makes a regulated
decision, and produces the evidence a second-line reviewer needs to approve them.

- `PLAN.md` — the four-week schedule and who does what
- `BUILD.md` — the specification and task tracker
- `docs/` — model selection, distillation note

## Run the Week 1 gate

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]" -e ../synthetic-data-designer
.venv/bin/python scripts/build_sample_pack.py --n 700 --keep 20 --seed 7
.venv/bin/python scripts/demo_gate.py
.venv/bin/pytest -q
```

`demo_gate.py` shows one generated referred case, a briefing that reads well and
omits the deciding fact, a briefing that surfaces it, and the omission check's
verdict on each. No model is called — the catch is arithmetic.

## What is where

| | |
|---|---|
| `specs/credit_underwriting.yaml` | The SDD recipe. A hidden capacity tier drives the observables; decoy fields have no path to the outcome. |
| `scripts/build_sample_pack.py` | SDD cases → scorecard → referred → attribution → rendered documents → `items.jsonl`. The answer key stays in `answer_key.json`, never in the items. |
| `src/evidence/contracts/` | The item format and check result shape. Proposed for the Friday freeze. |
| `src/evidence/checks/omission.py` | `material_omission`. Exact match, then similarity with mandatory numbers or polarity words, then missing. Passes only at full marks. |
| `packs/underwriter-sample/` | Twenty referred cases, built. |

## Placeholders

The rule for *which* facts a briefing must surface (`omission_targets()` in the
pack builder) is a placeholder pending the materiality definition from Luca.
Replace the rule; do not tune the check around it.
