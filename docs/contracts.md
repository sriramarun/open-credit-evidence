# The agreed formats — for Clyde

Three records cross the boundary between the pack side (Sriram) and the engine side
(Clyde). Once frozen, neither of us changes them without the other. The typed versions
are in `src/evidence/contracts/`; this page is the same thing as JSON so it can be read
without opening Python.

**Freeze target: Tuesday 15 Sep.** If any field is wrong for the engine, say so now.

---

## 1. Item — what the pack gives the engine

One line of `packs/<pack>/items.jsonl`. Typed as `BenchmarkItem` in `contracts/item.py`.

```jsonc
{
  "item_id": "underwriter-sample:case_review:APP000044:complete",
  "pack": "underwriter-sample",
  "domain": "credit_underwriting",
  "task": "case_review",

  "prompt": "You are supporting an underwriter. This application was referred ...",
  "context": [
    { "renderer": "application_form", "variant": "complete", "content": "# Personal Loan Application ..." },
    { "renderer": "bureau_summary",   "variant": "complete", "content": "# Credit Bureau Summary ..." }
  ],

  "deterministic_checks": ["material_omission"],
  "judges": [],
  "tags": { "difficulty": "near_boundary", "variant": "complete", "policy_dim": "oversight" },

  "grading": {
    "disposition": "refer",
    "top_n": 1,
    "driver_refs":   ["dti_ratio"],
    "driver_labels": { "dti_ratio": "debt-to-income ratio of 47% exceeds the 40% policy limit" },
    "driver_aliases": { "dti_ratio": ["debt to income", "DTI", "debt service", "..."] },
    "driver_directions": { "dti_ratio": "decreases" },
    "decoy_refs":    ["age_band", "dependants", "employer_name", "postcode_district", "..."],
    "decoy_aliases": { "tenure_months": ["time in role", "..."] },
    "omission_refs":   ["dti_ratio", "policy_limit_dti"],
    "omission_labels": { "dti_ratio": "...", "policy_limit_dti": "the 40% debt-to-income policy limit" },
    "omission_aliases": { "dti_ratio": ["47%", "exceeds the 40%", "..."], "policy_limit_dti": ["40%", "..."] },
    "flip_refs": [ { "ref": "gross_annual", "direction": "increase" } ],
    "contradiction_refs": [],
    "contradiction_labels": {}
  },

  "counterfactual_of": null,
  "perturbation_kind": null,
  "expected_disposition_change": null
}
```

**What the engine does with it:** send `prompt` as the system message and the joined
`context` contents as the user message (or, with RAG, retrieve from `context` first).
Pass the whole item to every check named in `deterministic_checks`. Never read `grading`
for anything except grading.

**What is deliberately absent:** scores, margins, contributions, flip thresholds. The
loader should refuse an item that carries any key named `score`, `margin`,
`contributions` or `threshold` — that is a leaked answer key.

---

## 2. Transcript — what the runner writes per item

Typed as `Transcript` in `contracts/transcript.py`. **New — not yet frozen.** One per
(item, system under test).

```jsonc
{
  "item_id": "underwriter-sample:case_review:APP000044:complete",
  "run_id": "2026-09-16T10:22:01Z-8f21",
  "sut": {
    "model_id": "nvidia/nemotron-3.5-lightning-30b-a3b",
    "prompt_version": "0f7c3b98eca20e37",
    "params": { "temperature": 0.0, "top_p": 1.0, "max_tokens": 2048, "seed": 7, "enable_thinking": false }
  },
  "system_prompt": "...",
  "user_prompt": "...",
  "retrieved": [
    { "renderer": "application_form", "chunk_id": "application_form#0", "score": 0.39, "text": "..." }
  ],
  "output": "**Case Summary for Underwriter Review: APP000044** ...",
  "latency_ms": 101475,
  "tokens_in": 439,
  "tokens_out": 598,
  "provider_id": "chatcmpl-...",
  "started_at": "2026-09-16T10:22:03Z",
  "sha256": "..."
}
```

`retrieved` is the field that matters for RAG. If the chunk containing the ratio was never
retrieved, an omission is a retrieval failure, not a model failure, and the evidence pack
has to say which. Empty list means the model was handed everything.

The adapter in `src/evidence/adapters/nvidia_build.py` already returns `model_id`,
`prompt_version`, `params`, `latency_ms`, `tokens_in`, `tokens_out` and `provider_id`.

---

## 3. Check result — what every check returns

Typed as `CheckResult` in `contracts/check.py`; `.to_score()` gives the stored form.

```jsonc
{
  "judge": "check:material_omission",
  "judge_trace_id": null,
  "value": 0.5,
  "passed": false,
  "detail": "omitted 1/2 material fact(s): ['the 40% debt-to-income policy limit']",
  "evidence": [
    { "ref": "dti_ratio",        "matched": true,  "method": "exact", "form": "47%", "span": [612, 615] },
    { "ref": "policy_limit_dti", "matched": false, "method": null }
  ],
  "needs_audit": false
}
```

A judge result uses the same shape with `"judge": "judge:<id>@<version>"` and a real
`judge_trace_id`. **`needs_audit` is mandatory reporting** — the evidence pack shows the
count of results that leaned on similarity matching.

---

## 4. Where things go on disk

```
runs/<run_id>/
  run_manifest.json          pack id + sha256, SUT pins, judge pins, engine commit, seed, env, timings
  transcripts/<item_id>.json one Transcript each
  results/<item_id>.json     { "item_id", "checks": [CheckResult...], "judges": [CheckResult...] }
  results.json               aggregated: by obligation → by check → by difficulty; every number at a stable JSON path
  artifacts/                 anything else, content-addressed by sha256
```

The runner must be **resumable**: if `transcripts/<item_id>.json` exists with a matching
`sut` block, skip the call. Free-endpoint latency is 100–150 s per call, so a killed run
that restarts from zero costs an afternoon.

---

## Calls the engine makes

```python
from evidence.adapters.nvidia_build import chat, embed
from evidence.checks import run_checks

r = chat("assistant", system=item.prompt, user=joined_context)       # -> ChatResponse
results = run_checks(item.deterministic_checks, output=r.text, item=item)
```

Rate limit on the account: 40 requests/minute. One worker is fine; the endpoint is the
bottleneck, not us.
