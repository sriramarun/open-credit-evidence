# Product plan — Credit Evidence Engine, end to end

Written 20 September 2026. `PLAN.md` is the four-week Codefest schedule. This
document is the plan for the product a regulated lender would actually deploy,
starting from what the Codefest leaves behind on 7 October. Dates are months
after the Codefest (M1 = October–November 2026). Effort is in person-weeks (pw)
for a team of three, growing to five in Phase 3.

## 1. What the product is

A lender puts an AI assistant in a regulated decision workflow — today, the
underwriter referral queue. Before the assistant is allowed near a real case, and
continuously after, the lender must be able to show a validator or a supervisor
that the assistant told the human what mattered. The Credit Evidence Engine is
the system that produces that showing.

It has four parts a buyer can point at:

| Part | What it is | Who touches it |
|---|---|---|
| **Packs** | Generated case sets with ground truth computed by construction: the spec, the scorecard, the documents, the sealed marking key, the obligations map | Model risk / validation team writes or adapts; the engine consumes |
| **Engine** | Runs a pack against an assistant, N repeats, records everything, runs the checks and the judge, aggregates by obligation | Runs in the lender's environment, on their GPUs |
| **Evidence pack** | The output: report by article, results, transcripts, manifest, checksums, attestation. Verifiable by anyone with the verifier | Validators, internal audit, supervisors |
| **Assurance** | How the engine's own parts are trusted: judge calibration, check tests, pack leak tests, run-over-run diffs, release provenance | The lender's second line, and us |

What it is not: it does not make or score the credit decision; it does not grade
regulatory compliance; it does not measure population fairness. Those are stated
on every evidence pack as NOT COVERED.

## 2. What exists on 7 October (planned Codefest end state)

- One domain pack (underwriter referrals, 20 cases, three documents), the SDD
  spec and scorecard that produced it, and the tests that prove the hidden tier
  does not leak.
- Contracts: item, transcript, check result, run manifest.
- Checks: material_omission, numeric_fidelity, decoy_citation, flip_accuracy,
  repeat agreement. Judge: readability with regulation passage, Nano on-prem,
  calibrated against Ultra and one human.
- Runner, check executor, aggregation, evidence pack writer, verifier, CLI.
- Adapters: OpenAI-compatible endpoints (NVIDIA Build, NIM, vLLM).
- One NeMo Evaluator benchmark wrapper. Apache 2.0 release.

Everything below builds on this; nothing below assumes it is thrown away.

## 3. Phases

### Phase 1 — Hardening (M1–M2, ~18 pw)

Purpose: turn the Codefest code into something a validation team can run
unattended and trust the output of.

| Work | Why | Done when |
|---|---|---|
| Pack format v1.0 frozen, with a JSON schema and a `pack validate` command | Packs are the interface between the lender's validators and the engine; they must be stable before anyone writes one | Schema published; the sample pack validates; a deliberately broken pack is rejected with a line number |
| Pack leak test suite as a product feature | A pack whose marking key can be inferred from the documents proves nothing | `pack audit` reports: hidden columns absent, decoy–outcome correlation, duplicate cases, key not in documents |
| Materiality definition as a pluggable rule set | The Codefest placeholder (top driver + breached limit + recent adverse) is one policy; lenders have their own | Materiality rules are a YAML per pack, versioned; Luca's definition ships as the default |
| Checks: `contradiction_recall`, `injection_resistance`, `driver_recall` | Complete the battery the obligations map promises | Each with tests, a negative control, and an entry in the obligations map |
| Judge: agreement study at scale (200 blind cases, two humans) | One human on 20 cases is a Codefest number, not a validation number | Inter-rater agreement and judge–human agreement published in the pack's assurance section |
| Runner: resumable, rate-limited, concurrent, deterministic ordering | Real packs are hundreds of cases × repeats | 500 × 3 completes on one GPU node overnight without supervision; a killed run resumes |
| Evidence pack: signed (Sigstore or GPG), named attester block, verifier as a standalone static binary | A supervisor must be able to verify without installing Python | `evidence verify` runs from a single file on a clean machine |
| Release provenance: SBOM, pinned images, reproducible build | Second line will ask what exactly produced the pack | Every evidence pack names the engine build hash and its SBOM |

### Phase 2 — Second domain and pack authoring (M3–M4, ~20 pw)

Purpose: prove the framework is not one clever pack. The second domain forces
every domain-specific assumption out of the engine.

| Work | Why | Done when |
|---|---|---|
| Portfolio surveillance pack: accounts over time, limits crossed, an assistant that briefs the portfolio manager | Different shape — time series, many accounts, one briefing — same obligations | Pack validates; the ceiling test (how much of the available signal the assistant used) runs |
| Pack authoring guide and starter kit | A lender's validation team must be able to write a pack for their own scorecard without us | A person outside the team builds a third pack (e.g., SME lending) from the guide in under two weeks |
| SDD integration as a library call, not a script | Case generation is a product step | `pack generate spec.yaml --n 500 --seed 7` produces a valid pack |
| Regulation corpus as a versioned artefact | Regulations move (Digital Omnibus); the pack must say which version of which text the judge saw | Corpus has a version, a changelog, a date; the manifest records it |
| Assistant adapters beyond a chat endpoint | Real assistants are agents with tools and retrieval, not one prompt | Adapter for a LangChain/LangGraph agent and for a "bring your own function"; the tool envelope records tool calls in the transcript |
| Comparison runs: two assistants, one pack, side by side | The buying question is "which assistant, and is the upgrade safer" | `evidence diff run-a run-b` by check, by obligation, with confidence intervals |

### Phase 3 — Deployable in a bank (M5–M7, ~30 pw, team of five)

Purpose: run inside a lender's perimeter, under their controls, on a schedule.

| Work | Why | Done when |
|---|---|---|
| Deployment: Helm chart / OpenShift templates; engine, judge NIM, assistant NIM, Milvus, object store | Banks run Kubernetes on-prem or in a private cloud; nothing may call out | Fresh cluster to first evidence pack in one day, air-gapped |
| Identity and access: SSO, roles (author, runner, attester, reader), audit log of every run and every read of an evidence pack | Second-line and audit requirements | Every action attributable to a person; log exportable |
| Scheduled and triggered runs | Continuous assessment (SR 26-2 ongoing monitoring; AI Act post-market monitoring) | A run fires on assistant version change and weekly; gates fail a deployment pipeline |
| Run registry and history | "Show me every run of this assistant since go-live" | Registry with search; run-over-run trend per check |
| Evidence pack templates for provider and deployer | The AI Act splits obligations between the assistant's vendor and the lender | Two report layouts from one run; each says which obligations it addresses |
| Read-only web viewer for evidence packs | Validators and auditors will not open JSON | Pack renders in a browser; every number links to its transcript |
| Data handling: no case content leaves the cluster; retention policy; deletion | Even synthetic packs mirror real formats and policies | Documented data flow; retention configurable; deletion verified |
| Performance: 1,000 cases × 3 repeats in under four hours on two GPUs | Packs will grow | Benchmark published per release |

### Phase 4 — Assurance and external validation (M8–M10, ~16 pw)

Purpose: the engine is itself a model-adjacent system; it must meet the standard
it evidences.

| Work | Why | Done when |
|---|---|---|
| Independent review of the check implementations and the pack leak tests | Second-line will ask who checked the checker | Review report published; findings closed |
| Judge revalidation procedure | Model risk policy requires periodic revalidation | Documented cadence, thresholds, and the retrain procedure; one cycle executed |
| Conformity mapping document per obligation | Maps each check to the article text and to harmonised standards as they land | Reviewed by external counsel or a Big-4 model-risk practice |
| Reference deployment with one lender or a public development bank | Real users, real scorecard, real validators | One evidence pack accepted by a real second line as validation input |
| Public benchmark: the sample pack run against several open assistants, results published | Establishes the pack as a reference and drives adoption | Results page with methodology; two outside teams reproduce a run |

## 4. Architecture at product scale

```
 Pack authoring                      Engine (in the lender's cluster)                     Consumers
 ─────────────                       ────────────────────────────────                     ─────────
 spec.yaml ──┐                       ┌────────────┐   ┌──────────────┐   ┌────────────┐
 scorecard ──┼─ pack generate ──▶    │  runner    │──▶│ check exec   │──▶│ aggregate  │──▶ evidence pack ──▶ viewer / verify
 materiality ┘   pack audit          │ N repeats  │   │ judge exec   │   │ by article │        │              (validators,
                                     └─────┬──────┘   └──────┬───────┘   └────────────┘        │               auditors,
                                           │                 │                                  ▼               supervisors)
                                    assistant under test   judge NIM (Nano)               run registry
                                    (NIM / agent / BYO)    regulation corpus (Milvus)     signed, checksummed
                                                                                          audit log · SSO
```

Everything inside "Engine" runs without network egress. The only inbound
artefacts are the pack, the engine release, and the regulation corpus version.

## 5. Team and roles

| Role | Codefest | Product |
|---|---|---|
| Credit data and packs (Sriram) | Cases, scorecard, checks, models | Pack format, authoring kit, judge assurance |
| Backend (Clyde) | Runner, evidence pack, verifier | Engine, deployment, registry, security |
| Economics and regulation (Luca) | Materiality, rubric, obligations | Materiality rule sets, conformity mapping, human studies, corpus |
| Platform engineer (new, Phase 3) | — | Helm/OpenShift, SSO, audit log, air-gap |
| Validator-in-residence (new, Phase 3, part-time) | — | Someone who has done second-line validation at a bank; reviews every pack and report layout |

## 6. Decisions to make, and when

| Decision | By | Options |
|---|---|---|
| Pack format licence and governance | End of Phase 1 | Apache 2.0 code with a CC-BY pack spec; or everything Apache 2.0 |
| Judge model policy | End of Phase 1 | Nemotron only; or "any open model that passes the agreement study", published per release |
| Signing scheme | Phase 1 | Sigstore keyless vs organisation GPG; banks often require the latter |
| Hosted offering | Phase 3 | None (on-prem only); or a hosted pack authoring and viewer service with no case content |
| Commercial model | Phase 2 | Open core with paid packs and support; or services around an entirely open product |

## 7. Risks

| Risk | Effect | Response |
|---|---|---|
| A lender's assistant is an agent with tools we cannot observe | Transcripts incomplete; checks weaker | Tool envelope in Phase 2; if the vendor will not expose tool calls, the pack says so under limitations |
| Materiality is contested between the lender's first and second line | Pack disputes | Materiality is a versioned rule set the second line owns; the engine records which version ran |
| Regulation text or dates change | Judge citations stale | Corpus versioned; manifest records it; a re-run with the new corpus is one command |
| Judge drifts after base-model updates | Readability scores shift | Revalidation cadence (Phase 4); the deterministic checks do not depend on the judge |
| Synthetic packs dismissed as "not real data" | Adoption | The argument is in `docs/verifiers-law.md`; the reference deployment (Phase 4) is the answer in practice |
| Team of three through Phase 2 | Slips | Phases 1–2 are scoped for three; Phase 3 hires are in the plan, not assumed early |

## 8. Milestones

| When | Milestone |
|---|---|
| 7 Oct 2026 | Codefest release: one pack, full battery, on-prem, evidence pack, verifier |
| M2 | v1.0: pack format frozen, signed evidence packs, standalone verifier, judge agreement at scale |
| M4 | v1.5: second domain, authoring kit proven by an outsider, assistant-agent adapter, `evidence diff` |
| M7 | v2.0: air-gapped cluster deployment, SSO and audit log, scheduled runs with gates, web viewer |
| M10 | External review closed; one reference deployment; public benchmark published |
