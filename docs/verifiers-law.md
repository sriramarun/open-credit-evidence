# Verifier's Law, and what it means for this framework

> Tasks that may be difficult to perform but easy to verify are especially well
> suited for agentic automation. When verification itself is slow, ambiguous, or
> delayed, safe automation becomes much harder.
>
> — Faraz Shafiq, Head of AI, Wells Fargo (paraphrased from a 2026 panel)

Use this in the final presentation, right after "the problem" and before "one
command". It says in one line why the product is shaped the way it is.

## The one-line version

**We automate what can be verified in seconds, and hand the human the evidence for
the rest. Our checks are the verifier.**

## Why it fits us

Ground truth by construction exists to make verification fast and unambiguous.
The marking key for every case is computed before any model runs, from a scorecard
we wrote, on data we generated. Verifying a briefing is then a string or number
comparison, not a judgement. That is the whole reason the framework can say
"evidence" rather than "opinion".

It also explains the boundary of the product without argument:

- The assistant **compiles** the case file (hard to do, easy to verify) — automate.
- The underwriter **decides** (easy to do, verifiable only 12–24 months later, when
  the loan defaults or does not) — human.
- Whether the deployment is **compliant** (ambiguous by nature) — we produce
  evidence a reviewer can check; we do not grade it.

## The tasks, sorted

### Tier 1 — hard to do, easy to verify: automate, and this is the evidence

| Task the assistant does | Why it is hard | The verifier | Time |
|---|---|---|---|
| State every fact the decision turned on | Three documents, ~20 fields, a few matter | `material_omission` against the marking key | instant |
| Use only numbers that are in the file | On 16 Sep, 8 of 10 briefings stated a wrong ratio | `numeric_fidelity` — every number must be in, or derivable from, the case file | instant |
| Ignore fields with no bearing on the outcome | Age band, dependants, postcode look relevant | `decoy_citation` — decoys are known by construction | instant |
| Say what would have to change | Needs the policy, not a restatement of it | `flip_refs` — field and direction | instant |
| Give the same verdict every time | Serving is not deterministic | N runs, agreement rate | minutes |
| Surveillance: flag accounts over a limit | Thousands of rows, several limits | recompute the limit | instant |
| Keep the evidence pack intact | — | hash chain, tamper test | instant |

### Tier 2 — verifiable, but slowly or by agreement: a judge, calibrated by humans, never the evidence

| Task | Why verification is slow |
|---|---|
| Is the briefing intelligible and actionable? | No formula. Nemotron Ultra grades it; the agreement study checks Ultra against Luca |
| Does it cite the right regulation passage? | Verifiable only against a curated corpus — the regulation-RAG work |

### Tier 3 — verification is delayed or ambiguous: the human keeps it

| Task | Why |
|---|---|
| Should this referred loan be approved? | Outcome known in 12–24 months |
| Is the deployment compliant with Article 14? | Ambiguous; we evidence, we do not grade |
| Is the applicant treated fairly? | Needs population data and a definition the bank owns |

## What to say on the day

"Verifier's Law says automate the tasks that are easy to verify. Compiling a case
file is one of those — *if* you have a marking key. We build the marking key first,
by construction, so every check is a comparison, not an opinion. The judge model
grades readability, which is not easy to verify, so it is never the evidence. And
the decision itself is verified by the loan book in two years' time, so it stays
with the underwriter."

## Where this is used

- `PLAN.md` — the ten minutes, step 1.
- `BUILD.md` §9 — the claims table; every "Evidences" row is a Tier 1 check.
- Slide 3 of the team deck, if we get a line: "Our checks are the verifier."
