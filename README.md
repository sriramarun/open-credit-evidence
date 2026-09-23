# Credit Evidence Engine

Tells a bank whether a vendor's AI assistant is safe to put in front of its
underwriters, recommends changes the bank can make itself, proves those changes
work, and keeps checking after every vendor update.

The bank does not own the assistant and cannot retrain it. So every finding is
routed to whoever can act on it: a setting the bank controls (instructions, what
documents are handed in, how search works, the output template), a runtime guard,
or the vendor.

- `docs/USABLE_PRODUCT_PLAN.md` — what "usable" means, the flow, the build stages and their status
- `PLAN.md` — the Codefest schedule · `BUILD.md` — the original specification

## Set up

```bash
python3.13 -m venv .venv && .venv/bin/pip install -e ".[dev]" -e ../synthetic-data-designer
.venv/bin/python scripts/build_sample_pack.py --n 2000 --keep 60 --seed 7
.venv/bin/pytest -q
```

The command is `python -m evidence` (or `evidence` once installed with a current
setuptools). Everything below runs offline with the simulated assistant; swap
`sim-baseline` for `baseline` to run the real one named in `.env`.

## The flow

### 1. Validate — run the assistant on constructed cases and get an evidence pack

```bash
python -m evidence run --settings settings/sim-baseline.yaml --split proof
```

Puts every case to the assistant (three times each), checks every answer, and
writes `evidence/<run>/`, which contains:

| File | For |
|---|---|
| `reports/decision.html` | Model risk — GO / GO WITH CONDITIONS / NO-GO / INCONCLUSIVE, against the bank's `thresholds.yaml` |
| `reports/failures.html` | Business owner — one card per kind of failure, with a real example and its root cause |
| `reports/recommendations.html` | What to change, who can, the exact settings patch, how to prove it |
| `reports/regulation.html` | Compliance — which obligations this evidences, partly covers, or does not touch |
| `reports/vendor.html` | What only the vendor can fix, with cases they can reproduce |
| `reports/audit.html` | Matches a person should check, weakest first |
| `transcripts.jsonl`, `results.jsonl`, `aggregate.json`, … | The machine record everything above is computed from |

Every number in the views links to the records it counts. The simulated assistant
is the engine's test double; everything it produces is labelled **not evidence**.

### 2. Verify — nobody can change a number

```bash
python -m evidence verify evidence/<run>
```

Re-checks every file and recomputes every derived number from the transcripts. A
changed digit is rejected and named — even if the forger also regenerated the
checksums.

### 3. Prove a fix — before and after, case by case

Apply a recommended patch to a copy of the settings file, run the proof cases
again, and compare:

```bash
python -m evidence run  --settings settings/sim-with-review-triggers.yaml --split proof
python -m evidence diff evidence/sim-baseline-proof-… evidence/sim-with-review-triggers-proof-…
```

ACCEPT, REJECT or NO EFFECT under the bank's acceptance rule, with how many cases
the change helped and hurt and a 95% interval. Failures that survive a change to
their own lever are flagged for the vendor. A person then approves it:

```bash
python -m evidence approve changes/<record>       # needs the approver role in settings/roles.yaml
```

### 4. Guard production — check every live briefing before an underwriter sees it

```bash
python -m evidence guard --settings settings/sim-baseline.yaml --split proof   # pilot: referrals from the pack
python -m evidence guard --settings settings/baseline.yaml --referrals live.jsonl
```

Checks that need no answer key (the rules engine's reasons are stated, every
figure is in the file, every citation was given, no planted instruction obeyed).
On failure it retries with a pointer, up to three attempts, then escalates.
`guard/<name>/monitoring.html` leads with the **first-attempt pass rate**, so the
guard cannot hide an assistant getting worse.

### 5. Watch — re-validate when the vendor ships a new version

```bash
python -m evidence watch --settings settings/baseline.yaml --version 2026.10
```

Re-runs only if the model, endpoint, version or settings changed; diffs against
the last run; exits 1 if the new version is worse, so a pipeline can block it.

### Also

| Command | Does |
|---|---|
| `evidence sign <pack> --key ~/.ssh/id_ed25519` | Public-key signature (OpenSSH); `verify --allowed-signers` checks who signed |
| `evidence audit` | The hash-chained log of every run, diff, guard, approval — and whether it is intact |
| `evidence annotate <pack>` | Runs the optional agent slots, if any are switched on (all off by default) |
| `evidence monitor guard/<name>` | Rebuilds the monitoring report from a guard log |

## Settings

`settings/` holds one file per configuration of the assistant. Each changes one
thing from `baseline.yaml`, so a diff between two runs names one lever:

| File | What it is |
|---|---|
| `baseline.yaml` | The vendor's model, a plain instruction, the whole case file, the law corpus searched |
| `with-review-triggers.yaml` | Also hands in what the rules engine computed (the ratio, the reason codes) |
| `search-case-file.yaml` | Searches the case file instead of handing it over — shows a search miss |
| `sim-*.yaml` | The same, on the simulated assistant |
| `guard.yaml` | The production guard: reason codes, retries, what happens on failure |
| `roles.yaml` | Who may approve a change |

`corpus/` holds the law and policy passages the assistant may cite (EU passages
are short summaries for testing, not the legal text).

## What is where

| | |
|---|---|
| `src/evidence/checks/` | `material_omission`, `numeric_fidelity`, `decoy_citation`, `flip_accuracy`, `injection_resistance`, `citation_grounded`, and the production checks `referral_reason_stated`, `planted_instruction` |
| `src/evidence/runner.py` | Puts cases to the assistant; resumable, rate-limited, records everything |
| `src/evidence/derive.py` | One pure function from what happened to every number and view — the writer and the verifier both call it |
| `src/evidence/diagnose.py`, `recommend.py`, `decide.py` | Root cause and lever per failure (rules, no model); patches; go/no-go |
| `src/evidence/report/` | The readable views |
| `src/evidence/diff.py` | Proving a change |
| `src/evidence/guard.py` | The production guard and its monitoring |
| `src/evidence/audit.py`, `signing.py` | Audit log, roles, signatures |
| `src/evidence/slots.py` | Agent plug-in points, off by default |
| `src/evidence/adapters/` | The assistant under test: any OpenAI-compatible endpoint, a Python callable, or the simulated test double |
| `Dockerfile`, `deploy/openshift/` | Container and cluster templates (untested) |
