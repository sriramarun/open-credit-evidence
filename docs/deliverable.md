# The final deliverable, and the path back from it

Written 18 September 2026, with 19 days to the presentation on 7 October. This
page shows what the judges will see, then works backwards to what has to exist
for each part of it. Everything under "What the screen shows" is a mockup — it
is what we intend to show, not what exists today. The "What exists today" table
is exact.

## 1. What we deliver, in one sentence

A public Apache 2.0 repository that, from a fresh clone and one command, runs an
AI underwriting assistant over a pack of generated loan cases, checks each
briefing against ground truth computed before the model ran, and writes a
tamper-evident evidence pack organised by EU AI Act article — with the assistant,
the retriever and a distilled judge all running on our own GPU.

## 2. The demo, minute by minute

Ten minutes. Each step is one thing on screen.

| Min | On screen | What it proves | Criterion it speaks to |
|---|---|---|---|
| 0–1 | Slide: one referred loan, the briefing a Lightning assistant wrote, the ratio it states (41.6%) next to the real one (47.5%) | The problem: accurate-sounding, wrong, and a judge model gave it full marks | Uniqueness |
| 1–2 | Slide: Verifier's Law; our checks are the verifier; ground truth by construction | Why the approach is different from LLM-grades-LLM | Uniqueness |
| 2–4 | Terminal: `evidence run packs/underwriter-sample --sut lightning-nim --repeats 3` — live, on the node | It runs; 20 cases × 3 repeats in about two minutes on our own GPU | Demo, Technological quotient |
| 4–6 | Terminal: the results table — omission, numeric fidelity, decoy citation, agreement across repeats; then `evidence report` opens the evidence pack | The catch, named, per case; the pack organised by article | Demo, Viability |
| 6–7 | Terminal: `evidence verify` passes; change one digit in a transcript; `evidence verify` fails and names the file | Tamper-evident | Viability |
| 7–8 | Slide: judge agreement — Nano (fine-tuned, on-prem) vs Ultra (cloud) vs Luca | The judge runs on-prem and we know how much to trust it | Technological quotient |
| 8–9 | Slide: the same pack ran on NVIDIA Build on 15 Sep and on our node on 7 Oct; two lines of config changed; here is the manifest diff | Portable, reproducible, on-prem | Viability, Progress |
| 9–10 | Slide: what existed on 9 Sep; what exists today; the repo URL; public-sector use | Progress; relevance | Progress, Public sector |

Fallback: a recording of minutes 2–7 from the last rehearsal, in case the VPN or
the node is down on the day.

## 3. What the screen shows

### 3a. The run

```
$ evidence run packs/underwriter-sample --sut lightning-nim --repeats 3 --out runs/2026-10-07
pack       underwriter-sample  v1.2  20 items  3 documents each  sha 9f3a…
sut        nvidia/nemotron-3.5-lightning  http://rtx-3se-05-36:8000/v1  temp 0  seed 7
judge      nano-judge-lora-v3  http://rtx-3se-05-36:8001/v1  (teacher: nemotron-3-ultra, agreement 0.88)
checks     material_omission  numeric_fidelity  decoy_citation  flip_accuracy  readability(judge)

running 20 × 3 …  60/60  1m 52s

check               pass    fail   audit   note
material_omission   17/20   3/20   2       fails: APP000103 APP000212 APP000488 (40% limit not stated)
numeric_fidelity     9/20  11/20   0       11 briefings state a ratio not in the file
decoy_citation      12/20   8/20   0       age_band ×6, dependants ×3
flip_accuracy       18/20   2/20   1
readability (0–2)   mean 1.85         nano judge; 3 cases below 1.5

repeats             verdict agreement 54/60 (0.90); 6 flips, all numeric_fidelity
wrote runs/2026-10-07/  (manifest, results.jsonl, 60 transcripts, evidence pack)
```

### 3b. The evidence pack

```
runs/2026-10-07/
├── manifest.json          what ran: pack sha, model ids, endpoints, prompt hashes, seeds, git hash
├── results.jsonl          one line per (item, repeat, check)
├── transcripts/           60 files: prompt, retrieved sections, response, tokens, latency, endpoint
├── evidence/
│   ├── report.md          the pack, by obligation (below)
│   ├── obligations.yaml   what is claimed at what level, and what is not claimed
│   └── attestation.json   who ran it, when, with which verifier version
└── checksums.sha256       every file above; verify recomputes and compares
```

`report.md`, abridged — this is what a validator or supervisor reads:

```
# Evidence pack — underwriter-sample v1.2 — run 2026-10-07

## Article 15 — accuracy, robustness            level: EVIDENCES
numeric_fidelity   9/20 pass.  11 briefings state a debt-service ratio absent
                   from the case file (range 39.6–44.7%; true values 41–52%).
                   Every instance listed in results.jsonl with the number and
                   the file it should have come from.
repeat agreement   0.90 over 3 runs, seed pinned. Non-determinism is a property
                   of the serving stack (vLLM MoE batching), recorded, not claimed away.

## Article 14 — human oversight                  level: EVIDENCES
material_omission  17/20 pass. 3 briefings omit the 40% policy limit the
                   referral turned on; the underwriter cannot see the rule.
decoy_citation     12/20 pass. 6 briefings cite age band as a factor; it has
                   zero weight in the decision and is a protected characteristic.
flip_accuracy      18/20 pass.
readability        mean 1.85 (judge: nano-judge-lora-v3, agreement with Ultra 0.88,
                   with human reviewer 0.85 on 20 blind cases)

## Article 13 — transparency                     level: CONTRIBUTES
## Article 9  — risk management                  level: CONTRIBUTES
## Articles 10, 12, 17, 43                       NOT COVERED — see obligations.yaml

## How this was produced
pack generated by Synthetic Data Designer spec credit_underwriting.yaml (sha …),
scorecard v1 (weights listed), ground truth computed before any model call.
Integrity: checksums.sha256; verify with `evidence verify runs/2026-10-07`.
```

### 3c. The tamper test

```
$ evidence verify runs/2026-10-07
60 transcripts, 1 manifest, 1 results file, 3 evidence files: all checksums match.  OK

$ sed -i 's/41.58%/40.0%/' runs/2026-10-07/transcripts/APP000044-r1.json
$ evidence verify runs/2026-10-07
transcripts/APP000044-r1.json: checksum mismatch (expected 3c1f…, got 88a0…).  FAIL
```

### 3d. The judge slide

| | Agreement with Ultra (exact) | Within one point | With Luca (20 blind) |
|---|---|---|---|
| Nano 9B, no fine-tune | 0.61 | 0.88 | 0.60 |
| Nano 9B + LoRA v3 | 0.88 | 0.97 | 0.85 |
| Ultra (teacher) | — | — | 0.90 |

Numbers above are targets from `docs/nano-judge-plan.md`, not results.

### 3e. The repository

```
open-credit-evidence/            Apache 2.0
├── packs/underwriter-sample/    20 items, 3 documents each, obligations.yaml, README with findings
├── specs/credit_underwriting.yaml   the SDD recipe: hidden tier, observables, declared decoys
├── src/evidence/                contracts, checks, adapters (Build + NIM), runner, evidence, verify
├── scripts/cluster/             serve the assistant and the judge on a node
├── scripts/finetune/            the Nano judge: data build, train, evaluate
├── examples/nemo_evaluator/     the same pack as a NeMo Evaluator benchmark
├── notebooks/01…04              models smoke, cluster setup, nano judge, the run
└── docs/                        BUILD, PLAN, cluster, deliverable, verifiers-law, nano-judge-plan
```

## 4. What exists today (18 Sep)

| Part of the deliverable | State | Evidence |
|---|---|---|
| Ground truth by construction | **Done** | SDD spec, scorecard, 700 applications, 20 referred items with marking keys |
| Case file (3 documents) | **Done** | application, bureau, lending policy, rendered per item |
| Contracts (item, check, transcript) | **Done** | `src/evidence/contracts/`, 19 tests |
| `material_omission` | **Done** | `checks/omission.py`, 7 tests, exact → similarity → missing |
| Assistant on-prem | **Done** | Lightning NIM on `rtx-3se-05-36`, 2–3 s per briefing, adapter switches by `.env` |
| Adapter to Build and NIM, endpoint recorded | **Done** | `adapters/nvidia_build.py` |
| Minimal retrieval | Exists, not in the path | `adapters/rag.py`; ranked policy over data on first run |
| `numeric_fidelity`, `decoy_citation`, `flip_accuracy` | **Not built** | ground truth for all three already in the marking key |
| Runner (items × repeats → transcripts) | **Not built** | |
| Results table, aggregation by obligation | **Not built** | |
| Evidence pack writer, checksums, verify | **Not built** | |
| CLI (`run`, `report`, `verify`) | **Not built** | |
| Judge rubric with regulation passage | Rubric exists (2 fields); no passage, no `overridable` | |
| Nano judge | Model downloaded, LoRA smoke run in progress | `scripts/finetune/smoke_lora.py` |
| NeMo Evaluator adapter | **Not built**; API confirmed to fit | `docs/…` (see 18 Sep notes) |
| Deck slides 1–5 | Done for Day 1 | `docs/deck/` |

## 5. Backtracking: what has to exist, in dependency order

Read bottom-up: each row needs the rows above it. Dates are the latest each can
finish and still leave two rehearsals.

| # | Must exist | Needs | Owner | Latest finish |
|---|---|---|---|---|
| 1 | `numeric_fidelity` check — every number in the briefing found in the file or derivable from it | marking key (done) | Sriram | Fri 19 Sep |
| 2 | `decoy_citation` check | marking key (done) | Sriram | Mon 22 Sep |
| 3 | Runner: pack × sut × repeats → transcripts, resumable, rate-limited | contracts (done), adapter (done) | Clyde | Tue 23 Sep |
| 4 | Check executor: every check over every transcript → `results.jsonl` | 1, 2, 3 | Clyde | Wed 24 Sep |
| 5 | `flip_accuracy` check | 4 | Sriram | Wed 24 Sep |
| 6 | Judge executor: rubric + retrieved passage → JSON score, per transcript | 3, Luca's rubric + corpus | Sriram | Wed 24 Sep |
| 7 | Materiality definition replacing the placeholder `omission_targets()` | Luca | Luca | Wed 24 Sep |
| 8 | Aggregation by obligation → results table | 4, 5, 6 | Clyde | Fri 26 Sep |
| 9 | Evidence pack writer: manifest, report.md, obligations, attestation, checksums | 8 | Clyde | Mon 29 Sep |
| 10 | `evidence verify` | 9 | Clyde | Mon 29 Sep |
| 11 | CLI: `run`, `report`, `verify` | 8, 9, 10 | Clyde | Tue 30 Sep |
| 12 | Nano judge: labels (400), baseline, LoRA, eval, served on port 8001 | 3, 6 | Sriram | Fri 3 Oct (gate) |
| 13 | Agreement study: Ultra vs Nano vs Luca on 20 blind cases | 12 | Luca | Fri 3 Oct |
| 14 | NeMo Evaluator adapter (`examples/`), 3 repeats, report | 3, 4 | Sriram | Wed 1 Oct |
| 15 | Double run on Build and on the node; manifest diff | 11 | Sriram | Thu 2 Oct |
| 16 | Cold-start test: fresh clone, one command | 11 | Clyde | Fri 3 Oct |
| 17 | Public release, RUNBOOK, OBLIGATIONS | 16 | Sriram | Mon 6 Oct |
| 18 | Two timed rehearsals + recording | 17 | all | Mon 6 Oct |
| 19 | Slides 6–10 (judge, portability, progress, public sector) | 12, 15 | Sriram | Tue 7 Oct 12:00 |

## 6. What we cut, in order, if we are late

1. Surveillance domain — already deferred; the deck says underwriter only.
2. `flip_accuracy` — the omission and numeric checks carry the demo.
3. NeMo Evaluator adapter — a bullet, not a slide.
4. Nano fine-tune — present Ultra as judge with the baseline numbers; the plan has this gate.
5. Regulation retrieval for the judge — rubric without passage; citation column blank.

Not cut under any circumstances: numeric_fidelity, the runner, the evidence pack,
verify, the cold-start test, the rehearsal.

## 7. Public-sector line, so it is not forgotten

The evidence pack's reader is a supervisor: ECB, BaFin, FCA, the Fed — public
bodies. The same assistant pattern runs inside public lenders and schemes: state
development banks, government-guaranteed SME and student loans, housing
authorities. Annex III 5(b) covers any creditworthiness assessment of a person,
not only by banks. One slide, one sentence, in minute 9.
