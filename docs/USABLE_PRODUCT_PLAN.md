# Build plan — a usable Credit Evidence Engine

Written 23 September 2026. This plan starts from what is actually in the
repository today and from one question: what does a bank need so that it can
buy this, run it against its own assistant, and act on what it says without us
in the room?

It replaces nothing yet. `PLAN.md` is the Codefest schedule and
`docs/PRODUCT_PLAN.md` is the earlier product plan; where they disagree with
this one, this one is the proposal.

---

## Build status — 23 September 2026

All six stages are built, tested (90 tests, offline, under ten seconds) and run end
to end from one command each. What that means stage by stage, and what is not done:

| Stage | Built | Not done |
|---|---|---|
| 0 Engine | Settings file; runner (resumable, rate-limited, three adapters: OpenAI-compatible, Python callable, simulated); five validation checks plus `citation_grounded`; 60 cases split tune/proof with 17 injected variants; aggregation; evidence pack writer and verifier that recomputes every number; `evidence run` | — |
| 1 Readable pack | One-page decision, failure cards, recommendations, regulation map, vendor findings, review queue, records — static HTML, every number linked, all re-rendered by the verifier | Visual design review with a real model-risk reader |
| 2 Diagnosis | Root cause and lever per failure by rules; ranked recommendations with paste-ready settings patches; vendor view; review queue split into figure-anchored and wording-only matches | — |
| 3 Prove a fix | `evidence diff`: paired per-case comparison, 95% interval, ACCEPT / REJECT / NO EFFECT under the bank's rule, change log, persisting causes flagged for the vendor; the change record is itself verifiable | — |
| 4 Production guard | Referral contract; production checks (reasons stated, figures in file, citations given, planted instruction); retry with pointer; escalation; monitoring report led by the first-attempt rate; `evidence watch` re-runs on a vendor version change | A real referral feed from a bank |
| 5 In a bank | Hash-chained audit log; roles and `evidence approve`; HMAC seal; OpenSSH public-key signatures; Dockerfile; OpenShift Job, CronJob and storage templates | **Untested:** the container and cluster templates. **Not built:** single sign-on (the bank's identity system), a hosted viewer, a verifier that runs without Python |
| Agent slots | Four plug-in points with deterministic defaults, off; notes stored separately, labelled, rejected if they contain a figure; `evidence annotate` | No agent is switched on or evaluated |

### What changed from the plan while building it

- **The headline check was too generous, and now isn't.** A briefing saying "within
  policy at 20% against the 40% limit" passed `material_omission`, because the material
  fact was "the 40% limit" rather than "exceeds the 40% limit", figures alone could
  satisfy a directional fact, and a negated alias ("not above the limit") counted. All
  three are fixed and tested. The simulated baseline's omission rate fell from 73% to
  43% — the old number was inflated.
- **A check that could not be exercised is no longer a pass.** When search never handed
  the planted instruction to the model, `injection_resistance` reported a pass. It now
  reports "not exercised" and is excluded from pass rates.
- **Too few results means INCONCLUSIVE**, not "GO WITH CONDITIONS".
- **The baseline hands over the whole case file** and searches only the law corpus.
  Word-overlap search with the task wording found none of the figures; a vendor's
  meaning-based search would do better, so the old baseline was unrealistically bad.
  `search-case-file.yaml` keeps the search-miss case for demonstration.
- **`citation_grounded` was added** — the check for the law corpus in the flow: every
  rule or article cited must appear in what the assistant was given.
- **The judge and the Nano fine-tune are out of scope**, as §9 proposed.

### First real run (23 Sep, the team's Nemotron Lightning NIM on the cluster)

33 proof cases × 2 repeats under each of two settings, 132 calls. Evidence packs in
`evidence/baseline-proof-15bb2f62-01d4c8bd` and
`evidence/with-review-triggers-proof-aec7de79-01d4c8bd`; change record under `changes/`.
All verify. These are pilot numbers on constructed cases, not a validation sign-off.

| | Baseline | With review triggers | Change (95% interval) |
|---|---|---|---|
| Verdict | NO-GO | INCONCLUSIVE (too few citations to judge) | |
| First-attempt pass rate | 45% | 73% | |
| `numeric_fidelity` | 64% | 91% | +27 pts (+12 to +42) — improved |
| `injection_resistance` | 60% | 100% | +40 pts (+3 to +77) — improved |
| `flip_accuracy` | 85% | 94% | +9 pts (0 to +18) — improved |
| `material_omission` | 92% | 92% | no clear change |
| `decoy_citation` | 86% | 89% | no clear change |

The engine's own top recommendation on the baseline was "give the assistant figures your
systems already computed". Applying it was **accepted** under the default rule. The top
remaining cause is blaming irrelevant fields (time in role, age), then figures stated
wrongly even with the right one in front of the model — a vendor finding. The model
also invented an applicant's age from an age band.

**The real run found three flaws in the checker, all fixed and tested:** numbered-list
markers were read as figures; correct "what would change" arithmetic (the affordable
debt cap, the income needed) was not declared derivable; durations restated in years
("176 months, 14 years and 8 months") were not recognised. Before the fixes the baseline
scored 15% on `numeric_fidelity`; the true figure is 64%. This is the argument for the
review queue and for keeping every check's evidence readable: the first real data always
finds something.

---

## 1. What "usable" means

Three people at a bank have to be able to do their job with the output.

| Person | Their question | What they must be able to do with our output |
|---|---|---|
| **Model risk / validation** (second line) | Is this assistant safe to put in front of underwriters? | Read one page and make a go / go-with-conditions / no-go call they can defend |
| **Business owner** (credit operations) | What is it getting wrong, and what do I change? | Read what failed, see why, and apply the recommended change |
| **Procurement / vendor manager** | Is the vendor's next version safer? Can I hold them to it? | Compare two versions side by side and send the vendor evidence it cannot argue with |

If any of the three cannot do that without us explaining it, the product is not
usable yet.

## 2. What the product does, in one line

**Tell a bank whether a vendor's AI assistant is safe to put in front of its
underwriters, recommend changes the bank can make itself, prove those changes
work, and keep checking after every vendor update.**

The bank does not own the assistant. It cannot retrain it. So every
recommendation is routed to whoever can act on it:

| Lever | Who controls it | Example |
|---|---|---|
| Instructions to the assistant | Bank | "State the referral reason first, with the figure" |
| What gets passed in | Bank | Pass the ratio the rules engine already computed, instead of making the model do arithmetic |
| Search settings and law corpus | Bank | Split the bureau report by table row; retrieve five passages instead of three |
| Output template | Bank | Required sections: reason, strengths, what would change the outcome |
| Runtime guard | Bank (our product) | Check every briefing, retry with a pointer, escalate |
| Model or version choice | Bank, from the vendor's options | Switch to the vendor's newer version |
| The model's own behaviour | **Vendor only** | Invents figures even when given the right one |

## 3. The flow

### Mode 1 — Validation (before go-live, and after every vendor update)

```
1. GENERATE   Invented, flagged loan applications with the answer known.
              Split into TUNE cases and PROOF cases from the start.
                  │
2. RUN        The assistant reads each case file and the law corpus and
              writes a briefing. Settings come from one file (settings.yaml).
              Everything is recorded: prompt, what search returned, output.
                  │
3. CHECK      Deterministic checks mark every briefing. No model involved.
                  │
4. DIAGNOSE   Simple rules give each failure a root cause:
              search missed it / model skipped it / number wrong / decoy
              blamed / hidden instruction followed.
                  │
5. RECOMMEND  Each root cause maps to a lever (table above).
                  │
6. PROVE      The bank applies a change → run again on PROOF cases only →
              compare before and after.
                  │
7. PACK       Machine record (source of truth) + four readable views.
```

### Mode 2 — Production (real loans, every day)

Real loans have no answer key, so production uses the checks that do not need
one. The bank's rules engine supplies a partial key: the reason codes it
referred the loan for.

```
Rules engine refers a loan, with reason codes (e.g. "DTI 47% > 40% limit")
        │
Assistant writes the briefing
        │
Production checks ──pass──► underwriter sees the briefing
        │
      fail
        │
Retry, with the check's message as the pointer (up to 3 attempts)
        │
Still failing ──► briefing shown with a failure card on top,
                  or the case goes to manual handling
        │
Everything logged → monthly monitoring report
```

The monitoring report leads with the **first-attempt pass rate**. If the guard
quietly fixes everything, nobody sees the assistant getting worse. The gap
between first-attempt and after-guard pass rates is the size of the problem the
guard is covering for.

## 4. Rules that do not bend

1. **The checks decide.** Nothing else sets pass or fail.
2. **The pack always reports the assistant's first attempt, unmodified.** Fixes
   are shown as before → change → after, never as a clean result.
3. **Fixes are settings changes, not edits to answers.** In validation nobody
   rewrites a briefing.
4. **Fixes are chosen on TUNE cases and proven on PROOF cases.** Whoever picks a
   fix never sees the PROOF cases' answers.
5. **Nobody types a number into a report.** Every figure is computed from the
   machine record and links back to it.
6. **A 100% pass rate is a warning, not a goal.** The pack shows what still fails.
7. **Agents are optional plug-ins, off by default.** Their output is labelled,
   stored separately from check results, and never supplies a number (§6).

## 5. Where we started (checked 23 Sep, before the build)

| Piece | State |
|---|---|
| Case generator (`scripts/build_sample_pack.py`, `specs/credit_underwriting.yaml`) | Works. 20 cases, three documents each (application form, bureau summary, lending policy). |
| Contracts: item, transcript, check result | Written |
| `material_omission` check | Built and tested. Similarity matches set `needs_audit`. |
| Other checks | Not built. `numeric_fidelity`, `decoy_citation`, `flip_accuracy`, `injection_resistance` |
| Model client and search (`adapters/nvidia_build.py`, `adapters/rag.py`) | Written |
| Runner | **Not built.** Nothing writes a `Transcript`. |
| Aggregation, evidence pack writer, verifier | **Not built** |
| Readable views | **None.** Output is JSON and terminal printouts. |
| Diagnosis, recommendations, before/after | **None** |
| Settings file for the assistant under test | **None.** Settings live in `.env` and code. |
| Production guard | **None** |
| Law corpus | Lending policy is one of the three documents. No regulation corpus. |
| What works end to end | `scripts/demo_gate.py` (no model) and `scripts/smoke_nvidia.py` (one model call), both printing to the terminal |

## 6. The build, stage by stage

Each stage ends with a test a person can run. Suggested module paths are under
`src/evidence/`.

### Stage 0 — The engine runs end to end

Without this nothing else has an input.

| Work | Where | Done when |
|---|---|---|
| Runner: puts each case to the assistant N times, writes one `Transcript` per call, respects the 40 requests/minute limit, resumes after a crash | `runner.py`, `contracts/run.py` (run manifest) | 60 cases × 3 repeats finish unattended; a killed run resumes |
| Settings file for the assistant under test: model, instructions, which fields are passed in, search settings (chunking, top-k) | `config/settings.py`, `settings.yaml` | Changing a setting needs no code change, and the file's hash is recorded in every transcript |
| Remaining checks: `numeric_fidelity`, `decoy_citation`, `flip_accuracy`, `injection_resistance` | `checks/` | Each has tests and a deliberately bad briefing that fails only that check |
| Grow the pack to 60+ cases, tagged `split: tune` or `split: proof` | `scripts/build_sample_pack.py` | Split is by case; a case never appears in both |
| Record where each material fact comes from (`omission_sources`: which document section holds the underlying figures) | `contracts/item.py`, pack builder | Needed by Stage 2 to tell a search miss from a model miss. Leaks nothing: `omission_refs` already travel with the item. |
| Aggregation: results by check, by difficulty, by split, by obligation | `aggregate.py` | One table per run, reproducible from the transcripts |
| Evidence pack writer and verifier (hash chain, tamper test) | `pack/writer.py`, `pack/verify.py` | Verifier accepts a clean pack; changing one digit makes it fail and name the number |
| One command | CLI: `evidence run` | Fresh clone → `evidence run --pack … --settings …` → pack on disk |

### Stage 1 — The pack is readable

Four views, generated from the machine record. Static HTML is enough; a web app
can come later.

| View | For | Contents | Where |
|---|---|---|---|
| **One-page decision** | Model risk | Go / go with conditions / no-go against stated thresholds. Top three risks. First-attempt pass rate per check. What still fails. What this does not test. | `report/decision.py` |
| **Failure cards** | Business owner | One card per failure type, with a real example: what was missed, where it was in the file, what search returned, why it mattered, root cause, recommended lever | `report/cards.py` |
| **Regulation map** | Compliance | Each obligation in `obligations.yaml`: which checks evidence it, the result, and what is not covered | `report/regmap.py` |
| **Machine record** | Auditor | What the pack writer produces; the verifier runs against this | Stage 0 |

- Every number in the three readable views is pulled from the record and links
  to the transcript or result it came from.
- Go / no-go thresholds live in a file the bank owns (`thresholds.yaml`), not in
  code.
- The `needs_audit` queue appears in the one-pager as a count, split into
  numeric-anchored and wording-only matches (see Stage 2).

**Done when:** someone outside the team reads the one-pager and can say what is
wrong with the assistant and whether they would deploy it.

### Stage 2 — Diagnosis and recommendations (rules, no agents)

| Work | How | Where |
|---|---|---|
| Root cause per failure | `material_omission` failed and the source section is **not** in what search returned → **search**. Source section **was** returned → **instructions or model**. `numeric_fidelity` failed and the right figure is in the file → **context or model**. Figure not derivable from the file at all → **invented, vendor**. Decoy cited → **instructions or model**. Hidden instruction followed → **safety, vendor**. | `diagnose/rules.py` |
| Lever per root cause | Fixed mapping from the §2 table, with template wording | `recommend/levers.py` |
| "Recommended changes" section | Grouped by lever, ranked by how many failures each would address | `report/recommend.py` |
| Vendor findings view | Failures only the vendor can fix, with reproducible case IDs, and evidence that the bank-side levers were tried first | `report/vendor.py` |
| Record how each similarity match was anchored | In `omission.py`, record whether the match was carried by the figures (`numeric`) or only by wording like "exceeds" (`wording`). Wording-only matches are the real review queue. | `checks/omission.py` |
| `needs_audit` becomes a list | Collected during aggregation, sorted weakest first, shown in the pack | `aggregate.py` |

**Done when:** every failure in a run has a root cause and a lever, and the
vendor view lists only what the bank cannot fix.

### Stage 3 — Prove a fix works

| Work | Where | Done when |
|---|---|---|
| `evidence diff run-a run-b`: per check and per root cause, on PROOF cases only, with the repeat spread shown | `diff.py`, `report/diff.py` | Two runs with different settings produce a readable before/after |
| Acceptance rule for a change: the targeted check improves on PROOF cases, and no other check gets worse by more than the repeat-to-repeat spread | `thresholds.yaml` | The diff view says ACCEPT or REJECT and why |
| Change log in the pack: which settings changed, from what, to what, and the diff that justified it | `pack/writer.py` | A reviewer can trace every change to its evidence |
| Adapters for other assistants: vendor APIs, assistants that use tools (tool calls recorded in the transcript) | `adapters/` | A new assistant is connected by editing `settings.yaml` |

**Done when:** a recommended change is applied, re-run on PROOF cases, and the
pack shows before → change → after with an ACCEPT.

### Stage 4 — Production guard

| Work | Where | Done when |
|---|---|---|
| Referral record input: application ID plus the rules engine's reason codes (field, value, limit) | `contracts/referral.py` | Contract fixed and documented for the bank's integration team |
| Production checks: `referral_reason_stated`, `numeric_fidelity` (against the live file), `citation_grounded` (every law cited exists in the corpus and was retrieved), `injection_resistance` | `guard/checks.py` | Each runs on a real briefing with no answer key |
| Retry with pointer: the failing check's message becomes the retry instruction; up to 3 attempts; each attempt checked again | `guard/retry.py` | A briefing that skips the referral reason is caught, retried, and passes or escalates |
| Escalation: briefing shown with a failure card, or case routed to manual handling (bank chooses) | `guard/escalate.py` | Both paths work |
| Guard log and monthly monitoring view: first-attempt pass rate, after-guard pass rate, escalations, by failure type, trend | `guard/log.py`, `report/monitoring.py` | The view leads with the first-attempt rate |
| Re-run the full validation pack on a vendor version change | CLI: `evidence run --on-version-change` | A new version produces a new pack and a diff against the last one |
| Law corpus as a versioned folder (one file per passage, version and date recorded in every manifest) | `corpus/` | `citation_grounded` resolves against it |

Until a bank supplies real reason codes, the guard is demonstrated on pack cases
with reason codes derived from the answer key's breached limits.

### Stage 5 — Runs inside a bank

- Installs on the bank's own infrastructure (OpenShift / Kubernetes), with no
  calls out of the network.
- Sign-in, roles (runs, approves changes, reads), and an audit log of every run
  and every approval.
- Signed packs; a verifier that runs as a single file on a clean machine.
- Scheduled runs and version-change triggers wired into the bank's deployment
  pipeline, so a failing pack blocks a vendor update.

## 7. Agent slots (built empty, switched off)

Each slot is an interface with a plain, non-agent default. An agent can replace
the default later, behind a setting, and only after it beats the default on a
measured task.

| Slot | Default now | Agent version later | Interface |
|---|---|---|---|
| `Diagnoser` | Stage 2 rules | Reads the transcript for cases the rules mark "unclear" | `slots.py` |
| `Proposer` | Template wording per lever | Drafts a specific instruction or settings change, which then goes through Stage 3 like any other | `slots.py` |
| `AuditHelper` | `needs_audit` list sorted weakest first | Writes the strongest argument that a wording-only match does **not** convey the fact; a person decides | `slots.py` |
| `Narrator` | Template sentences in the views | Writes the explanatory text in failure cards and the one-pager | `slots.py` |

For every slot:

- Output goes into a separate record (`AgentNote`: slot, model, prompt version,
  trace ID, text), never into `CheckResult`.
- Output is labelled as agent-written wherever it appears.
- Agent text never supplies a number.
- A `Proposer` change is only accepted through the Stage 3 diff, exactly like a
  human's.

## 8. Timeline

### To the final on Wednesday 7 October

| Dates | Sriram | Clyde |
|---|---|---|
| Thu 24 – Tue 29 Sep | Four remaining checks; pack to 60+ cases with tune/proof split; `omission_sources` | Runner; settings file; aggregation; pack writer; verifier |
| **Wed 30 Sep** | **Checkpoint: one command, 60 cases × 3 repeats, pack verifies, one changed digit fails it** | |
| Thu 1 – Mon 5 Oct | Stage 2 rules for omission and numeric failures; one manual before/after: change one setting (pass the computed ratio in), re-run PROOF cases | One-page decision view and failure cards; a simple before/after table |
| Mon 5 Oct | Code freeze | |
| Tue 6 – Wed 7 Oct | Rehearse; record a backup video | |

**What the audience sees on 7 October:**

1. The assistant's first attempt fails, including a briefing that is true, reads
   well, and leaves out the deciding fact.
2. The failure card names what was missed, where it was, and the root cause.
3. One settings change, recommended by the rules.
4. Re-run on PROOF cases: the pass rate moves, and the remaining failures are shown.
5. The one-page decision, generated from the pack; change a digit and the
   verifier rejects it.

**If behind, cut in this order:** `injection_resistance` → `flip_accuracy` →
before/after (show the recommendation only) → failure cards (keep the one-pager).
Never cut: runner, pack writer, verifier, one-page decision.

### After the Codefest

| When | Stages | Milestone |
|---|---|---|
| October – November | Rest of Stage 1 (regulation map, vendor view), Stage 2 complete, Stage 3 | A bank's validation team can run a full validation and apply a proven fix without us |
| December – January | Stage 4 | Production guard running on a pilot's referral queue, monthly monitoring report |
| February – April | Stage 5 | Installed inside a bank, with sign-in, audit log and version-change triggers |
| Any time after Stage 3 | Agent slots | Each turned on only after it beats its default |

## 9. Out of scope for a usable v1

| Not doing | Why |
|---|---|
| Readability judge and Nano fine-tune | Useful, but not needed for any of the three users in §1 to do their job. Adds a model that itself needs validating. Revisit after Stage 3. |
| Second domain (portfolio surveillance) | Proves generality, not usability |
| Web app | Static HTML views are enough for a pilot |
| Fairness analysis | Needs population data and a definition the bank owns |

## 10. Open ownership

Luca is no longer on the team. These were his and need an owner:

| Item | Needed by | Suggested |
|---|---|---|
| What counts as a material fact (the omission definitions) | Already in the pack; needs a named owner for changes | Sriram |
| Wording of "what this does not test" | Stage 1 one-pager | Sriram, reviewed by a mentor |
| `obligations.yaml` and the regulation map | Stage 1 | Sriram |
| Presentation script and delivery | 7 Oct | Decide this week |
| Independent review of weak (`needs_audit`) matches | Stage 2 | Nobody independent is left. Report the count and state that review was single-person. |

## 11. Risks

| Risk | Effect | Response |
|---|---|---|
| Runner not working by Tue 29 Sep | Nothing downstream can run | Sriram writes a 30-line loop against the assistant as a fallback; the proper runner replaces it later |
| 60 cases × 3 repeats is too slow at 40 requests/minute | Run takes hours | Use the on-node assistant, not the cloud endpoint; 60 × 3 = 180 calls |
| The rules can't place a failure | "Unclear" root causes in the pack | Report them as unclear, with the count. This is where the `Diagnoser` agent slot earns its place later. |
| A settings change helps one check and hurts another | A false "fix" | Acceptance rule in Stage 3 rejects it |
| The vendor exposes no settings at all | Only the vendor findings view is useful | Say so in the pack; the guard (Stage 4) still applies |
| Repeat runs disagree | Before/after looks like noise | Show the spread; only accept changes larger than it |

## 12. Words used

| Word | Meaning here |
|---|---|
| Assistant | The vendor's AI that writes the briefing. We test it; we don't own it. |
| Briefing | What the assistant writes for the underwriter about one referred loan |
| Check | A piece of code that marks a briefing pass or fail with no model involved |
| Answer key | What each invented case should have produced. Exists only because we built the cases. |
| TUNE / PROOF cases | Cases used to choose a fix / cases used to prove it. Kept separate so a fix can't just memorise. |
| Lever | Something that can be changed to fix a failure, and who controls it |
| Settings file | One file holding everything the bank can change about the assistant |
| First-attempt pass rate | How often the assistant passes without any retry. The honest measure. |
| Guard | Production checks plus retries plus escalation |
| Reason codes | Why the bank's rules engine referred the loan. A partial answer key for real loans. |
| Evidence pack | The machine record plus its readable views, hash-chained so tampering is detectable |
| `needs_audit` | A match found by similar wording rather than exact wording. Worth a person's look. |
| Agent slot | A place where an AI helper can be plugged in later, off by default |
