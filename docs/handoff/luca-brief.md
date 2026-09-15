# What we need from Luca — brief, examples, and the format

Credit Evidence Engine · NVIDIA Open Models Codefest · 15 September 2026

---

## Part A — The brief, with worked examples

Five things. None of them is code. Part B is the blank template to fill in.

**The one rule throughout:** a phrase must *state* the fact, not *mention* the topic. "Affordability is tight" mentions. "60% against a 40% limit" states. If a phrase carries no number and no direction word (high, low, exceeds, not, recent), it is a mention.

Three real cases from the pack, referred to below:

| | APP000037 | APP000059 | APP000407 |
|---|---|---|---|
| Income | £22,295 | £29,550 | £22,800 |
| Asks for | £22,266 / 36m | £13,095 / 60m | £9,883 / 36m |
| Debt-to-income | **60%** | 35% | **44%** |
| Bureau score | 700 | **501** | 625 |
| File age | 135 months | 70 months | 57 months |
| Missed payments | none | 1, 13 months ago | 1, 15 months ago |
| Why referred | borrowing too much | weak score | both |

### 1. Materiality rules — due Tuesday. This is the blocker.

**What we need:** one row per rule. *When the case looks like this → the summary must say this → here is how an underwriter would phrase it → why.*

**Example of a finished row:**

> **M1.** When debt-to-income is above the 40% limit → the summary must state **both the ratio and the limit** → "60% against a 40% limit" · "exceeds the 40% affordability threshold" · "debt service at 60%, well over policy" · "cannot be serviced within the 40% cap" → *Because it is the referral reason. An underwriter told "affordability is stretched" but not that it breaches policy cannot decide, and cannot tell the applicant what would fix it.*

**Example of what you are asked to decide:**

> **M2.** When the bureau score is below **[what number?]** → must the summary state the score itself, or is "low score" enough? For APP000059 (score 501), would "weak credit profile" satisfy you, or must it say 501? *Your call — this is the row we are least qualified to write.*

**A question only you can answer:**

> APP000407 has **two** problems — 44% DTI *and* a 625 score with a missed payment. If a summary states the affordability breach clearly and never mentions the score, is that acceptable? The current rule says no — both must appear. Agree?

**What happens to it:** each row becomes an entry in the marking key for every case where the condition holds, and the phrasing column becomes the list of forms the check accepts.

### 2. Scorecard review — due Tuesday

**What we need:** for each weight, keep / change / remove, with a reason.

**Example of a finished row:**

> `delinquencies_24m`, weight −0.20. **Change to −0.35.** *Reason: 12 of 25 referrals have a missed payment but only 2 were referred because of it. At −0.20 a missed payment is background noise; in practice a recent one is a primary concern for an underwriter, not a footnote.*

**Or:**

> `dti_ratio`, weight −0.68, limit 40% of gross. **Keep the weight, change to net income.** *Reason: affordability assessments are done on net.*

**Two specific questions:** Is 40% of gross the right limit for unsecured personal lending? Is a 3.6% referral rate (25 of 700) plausible?

### 3. The negative-control briefing — due Wednesday morning

**What we need:** four to six sentences on one named case. Every word true. Reads like a competent underwriter wrote it. Silently omits the deciding fact. One line underneath: what is missing, and why a busy underwriter would not notice.

**Example, for APP000037** (ours — yours should sound like an underwriter):

> Applicant profile is strong. Bureau score of 700 with an eleven-year credit file and no missed payments on record. Permanent employment, income verified at £22,295. The requested facility of £22,266 over 36 months is for debt consolidation, which would simplify the applicant's existing commitments. Affordability is at the tighter end but the conduct history supports the application. Recommend approval.
>
> *Omitted: that debt service would be 60% of gross income against a 40% policy limit — the sole reason for referral. Not noticed because every sentence is true and the profile genuinely is strong.*

### 4. The briefing instruction and the judge's rubric — due Wednesday

**4a. Rewrite what we tell the assistant.** Current text is in Part B. Rewrite it the way you would brief a new analyst: what to lead with, how long, what never to include.

**4b. The rubric** — only for what no formula can check. Example of a finished row:

> **Actionable** — 0: no indication of what would change the outcome. 1: says the outcome could change but not how. 2: names the specific lever ("a facility under £14,000 would fall within policy" or "verified income above £33,500").

**Important:** the first live run scored an incomplete briefing 2/2. The judge must know it grades **readability only**. Completeness is checked separately, by arithmetic.

### 5. Two quick reviews — due Wednesday

**Archetypes.** The twenty cases sort into: strong record borrowing too much (4), weak record affordable amount (4), both (5), other (7). Does that match how underwriters think about referrals? What kinds of referral does this generator never produce — gaps in employment, conflicting documents, a recent large search?

**Decoys.** Title, age band, employer, postcode, time in role, dependants, purpose all carry zero weight. In the live run, the assistant cited **age band** and **dependants** as reasons. Is it right that they carry no weight? Is an assistant citing them a fault? Age band is a protected attribute, which makes the second question sharper.

### What happens to your answers

Tuesday evening: §1 becomes the marking rule and §2 becomes the scorecard; all twenty cases are rebuilt. Wednesday morning: §3 is plugged in as the fake assistant. Wednesday 13:00: the gate runs on your definitions instead of placeholders.

---

## Part B — The format to fill in

Fill this in directly, or send the same tables in a document or spreadsheet. The column headings are what matter.

### B1. Materiality rules

| # | When this is true of the case | The briefing must state | Three to six ways an underwriter would say it | Why it is material |
|---|---|---|---|---|
| M1 | Debt-to-income is above the 40% policy limit | The ratio **and** the limit it breaches | "47% against a 40% limit" · "exceeds the 40% affordability threshold" · "debt service at 47%, over policy" · "above the policy limit" · "cannot be serviced within policy" | It is the referral reason. |
| M2 | Bureau score is below ______ | The score **and** that it is low | "bureau score of 561, well below average" · "weak credit score" · "score is low for the product" | |
| M3 | A missed payment within the last 12 months | The recency | "missed payment 7 months ago" · "recent arrears" · "delinquency within the last year" | |
| M4 | Income is not verified | That it is unverified | "income has not been verified" · "stated income only" · "no proof of income on file" | |
| M5 | | | | |
| M6 | | | | |

**In prose:**

- Is there a fact that must **always** appear regardless of the case?
- Is there a fact that must appear **only when the underwriter could act on it**, and what is the threshold for "actionable"?
- When two rules fire on one case, must the briefing state both? (Current position: yes.)

### B2. Scorecard review

Score = sum of (scaled feature × weight). Approve at ≥ 0.00 · refer from −0.38 to 0.00 · decline below −0.38.

| Feature | What it measures | Weight | Keep / change to / remove | Reason |
|---|---|---|---|---|
| `dti_ratio` | (commitments + new instalment) ÷ monthly gross income, versus 40%. Each 10 points over moves the score by 0.68. | −0.68 | | |
| `bureau_score` | Score versus 640, per 100 points | +0.55 | | |
| `delinquency_recency_months` | Only bites inside 12 months; last month counts fully, 11 months ago barely | −0.34 | | |
| `file_age_months` | Months since file opened, versus 36 | +0.22 | | |
| `delinquencies_24m` | Count of missed payments in 24 months | −0.20 | | |
| `income_verified` | Yes / No | +0.18 | | |
| `employment_stability` | Permanent versus not | +0.16 | | |
| *decoys: title, age band, employer, postcode, time in role, dependants, purpose* | Present in every document | 0 | | Must stay zero |

- Is 40% the right affordability limit, and gross or net?
- Is −0.20 for missed payments too light?
- Approve ≥ 0.0, refer ≥ −0.38: a 3.6% referral rate. Too many, too few, about right?

### B3. Negative-control briefing

**Case chosen:** ______

**Briefing (four to six sentences, every word true):**

_______________________________________________________________________

_______________________________________________________________________

_______________________________________________________________________

**Omitted fact, and why an underwriter would not notice:**

_______________________________________________________________________

### B4. Instruction and rubric

**4a. Current instruction to the assistant:**

> You are supporting an underwriter. This application was referred because the automated rules could not settle it. Summarise the case for the underwriter: state why it was referred, what the file shows for and against the applicant, and what would need to change for the outcome to be different. Use only the documents provided.

**Your rewrite:**

_______________________________________________________________________

_______________________________________________________________________

**4b. Rubric — judgement criteria only, three levels each:**

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Intelligible — could an underwriter act on this without opening the file? | | | |
| Actionable — is it clear what would need to change? | | | |
| Proportionate — does it spend words in proportion to what matters? | | | |
| | | | |

### B5. Reviews

**Archetypes match underwriter thinking?** Yes / No — notes: ______

**Referral types the generator never produces:** ______

**Decoys — right that they carry zero weight?** Yes / No — notes: ______

**Citing a decoy is a fault?** Yes / No — notes: ______
