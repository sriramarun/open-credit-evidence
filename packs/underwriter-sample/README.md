# underwriter-sample

Twenty referred personal-loan applications with a known answer, built for the Week 1
gate. This is what the assistant under test is given, and what it is marked against.

## What is here

| File | What it is | Committed |
|---|---|---|
| `items.jsonl` | The 20 cases as the assistant receives them — rendered documents plus the marking key. **This is the pack.** | yes |
| `referred_20.csv` | The same 20 as a table: observables, top driver, what a briefing must surface, decoys, archetype. | yes |
| `applications_700.csv` | Every application SDD generated, before the scorecard ran. 19 columns. The hidden capacity tier is not in it. | yes |
| `referred_cases_readable.md` | The 20 as plain documents with the marking key under each. For reading, not parsing. | yes |
| `manifest.json` | Checksums, seed, spec hash, population counts. | yes |
| `obligations.yaml` | Which EU AI Act articles this pack claims, at what level. | yes |
| `answer_key.json` | Scores, margins, per-feature contributions. **Never travels with the items.** | no — gitignored |
| `sdd_book.parquet` | The 700 as parquet. Regenerable from seed 7. | no — gitignored |

Rebuild everything with:

```bash
.venv/bin/python scripts/build_sample_pack.py --n 700 --keep 20 --seed 7
```

## How it was built

1. **Synthetic Data Designer generated 700 applications** from
   [`specs/credit_underwriting.yaml`](../../specs/credit_underwriting.yaml). Each applicant
   carries a hidden repayment-capacity tier that drives income, bureau score, commitments,
   file age and arrears through declared noise. The amount requested is deliberately
   independent of the tier — a good borrower can ask for too much. Seven fields (title, age
   band, employer, postcode, time in role, dependants, purpose) have no path to the outcome.
2. **A scorecard decided** approve / refer / decline and recorded every feature's contribution.
3. **The 25 referred cases were kept**, and the 20 closest to a decision line selected.
4. **Attribution became the marking key**: drivers ranked, decoys listed, omission targets
   set — the facts a briefing must surface.
5. **Documents were rendered** — an application form and a bureau summary — and checked
   for outcome words. None leak.

The rule for *which* facts are omission targets (top driver, any policy limit breached, any
recent adverse item) is a placeholder pending the materiality definition from Luca.

## What the loans show

**Population:** 523 approve, 152 decline, 25 refer. A 3.6% referral rate.

**The scorecard separates on affordability.** 99% of declines are over the 40%
debt-to-income limit; 10% of approves are. Median DTI runs 23% → 45% → 70% across
approve → refer → decline; median bureau score 733 → 652 → 612. The referral band sits
between the two on both dimensions rather than being noise.

**Why the 25 were referred:** 17 on debt-to-income, 5 on a low bureau score, 2 on missed
payments, 1 on unverified income. Referral is mostly an affordability question here, which
matches underwriting reality — conduct problems tend to decline outright; "can they actually
pay this" is what needs a human.

**The 20 kept are genuinely marginal.** Margin to the nearest decision line runs 0.023 to
0.154. Thirteen sit closer to approve, seven closer to decline.

**Decoys are independent, empirically.** Every signal field correlates with the bureau score
through the hidden tier — income +0.72, file age +0.67, commitments −0.63, delinquencies
−0.44. Time in role and dependants sit at −0.04 and −0.08. Across the categorical decoys,
mean bureau score varies by 20–34 points between levels, against a 164-point spread across
income tiers. That is noise at n=700.

### Three archetypes, three different briefings

| Archetype | Count | The material fact | The dangerous briefing |
|---|---|---|---|
| **Strong record, borrowing too much** — bureau ≥ 680, DTI over the limit | 4 | The amount. Conduct is not in question. | Leads with the excellent record, buries the ratio. This is the negative control. |
| **Weak record, affordable amount** — bureau < 640, DTI under 40% | 4 | The score. Affordability is fine. | Says "affordability is fine" and skips the score. |
| **Weak record and over the limit** — both | 5 | Two independent problems. | Surfaces one and not the other. Both are omission targets, so the check catches it. |
| Other | 7 | Mixed. | — |

This split is why the omission check has to be **per case**. A briefing template that always
leads with debt-to-income would pass the first group and fail the second. The marking key
tells the check which fact matters for *this* applicant.

### One thing to revisit in the recipe

12 of the 25 referred applicants have at least one missed payment, but only 2 were referred
*because* of it. Delinquencies are appearing as context rather than as a driver: the −0.20
weight is light against DTI's −0.68. Defensible as scorecard design, but if a recent missed
payment should carry more weight in a referral decision, it is one number in `WEIGHTS` in
`scripts/build_sample_pack.py`.

## The gate, on this pack

```bash
.venv/bin/python scripts/demo_gate.py --case APP000044
```

Prints one case, a briefing that reads well and omits the deciding fact, a briefing that
surfaces it, and the omission check's verdict on each. No model is called.
