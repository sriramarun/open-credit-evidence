# What we need from Luca, and in what shape

Five inputs. None of them is code. Fill this file in directly, or send the same tables in a
doc or a spreadsheet — the column headings are what matters, because each row maps
straight into the marking key.

The one rule that runs through all of it: **a phrase must *state* the fact, not *mention*
the topic.** "Affordability is somewhat tight" mentions the topic. "47% against a 40%
limit" states the fact. The first is how an assistant sounds informed while telling the
underwriter nothing; the second is what the check looks for. When in doubt, ask: does
this phrase carry a number or a direction (high, low, exceeds, not, recent)? If it
carries neither, it is a mention.

---

## 1. The materiality rules — due Tuesday, this is the blocker

**The question:** for a referred credit application, what must a briefing state for the
underwriter to be properly informed?

**The shape:** one row per rule. A rule is *when this is true about the case, the briefing
must say this*. Rules are conditional, because the material fact differs by case — for a
strong borrower asking for too much it is the amount; for a weak borrower asking for a
modest amount it is the score.

| # | When this is true of the case | The briefing must state | Three to six ways an underwriter would actually say it | Why it is material |
|---|---|---|---|---|
| M1 | Debt-to-income is above the 40% policy limit | The ratio **and** the limit it breaches | "47% against a 40% limit" · "exceeds the 40% affordability threshold" · "debt service at 47%, over policy" · "above the policy limit" · "cannot be serviced within policy" | It is the referral reason. An underwriter told "affordability is tight" but not the limit cannot decide. |
| M2 | Bureau score is below [Luca: what threshold?] | The score **and** that it is low | "bureau score of 561, well below average" · "weak credit score" · "score is low for the product" · "561 is subprime territory" | *(Luca)* |
| M3 | A missed payment within the last 12 months | The recency | "missed payment 7 months ago" · "recent arrears" · "delinquency within the last year" | *(Luca)* |
| M4 | Income is not verified | That it is unverified | "income has not been verified" · "stated income only" · "no proof of income on file" | *(Luca)* |
| M5 | *(Luca — anything else? e.g. employment type, file age, term versus purpose)* | | | |

**Also answer, in prose:**

- Is there a fact that must **always** appear in a briefing regardless of the case — the
  disposition reason, the amount requested, anything else?
- Is there a fact that must appear **only when the underwriter could act on it** — for
  example "a smaller facility would be approvable" — and if so, what is the threshold for
  "actionable"?
- When two rules fire on one case (weak score *and* over the limit), must the briefing state
  both, or is stating the larger one acceptable? Our current position is **both**, because a
  briefing that surfaces one problem and hides the other is still misleading.

**What happens to this:** each row becomes an entry in `omission_refs` for every case where
the condition holds, and column 4 becomes the alias list the check resolves against. The
current placeholder in the code is roughly M1 + M3 + "the top driver". Your rules replace it.

---

## 2. The scorecard review — due Tuesday

**The question:** does this decision rule look like lending to someone who knows lending?

The scorecard is a weighted sum. Each feature is scaled, multiplied by its weight, and the
total decides: approve at or above 0, refer down to −0.38, decline below that.

| Feature | What it measures | Weight | Keep / change to / remove | Reason |
|---|---|---|---|---|
| `dti_ratio` | (existing commitments + new instalment) ÷ monthly income, versus the 40% limit. Each 10 points over moves the score by 0.68. | −0.68 | | |
| `bureau_score` | Score versus 640, per 100 points | +0.55 | | |
| `delinquency_recency_months` | Only bites inside 12 months; a payment missed last month counts fully, one missed 11 months ago barely | −0.34 | | |
| `file_age_months` | Months since file opened, versus 36 | +0.22 | | |
| `delinquencies_24m` | Count of missed payments in 24 months | −0.20 | | |
| `income_verified` | Yes / No | +0.18 | | |
| `employment_stability` | Permanent versus not | +0.16 | | |
| *decoys: title, age band, employer, postcode, time in role, dependants, purpose* | Present in every document | 0 | | Must stay zero — see §5 |

**Two specific questions:**

- **Is 40% the right affordability limit** for an unsecured personal loan, and should it
  be gross or net income? (It is gross now.)
- **Is −0.20 for missed payments too light?** Twelve of the twenty-five referred cases have
  a missed payment; only two were referred *because* of it. Under this scorecard a missed
  payment is context, not a driver. Is that how it should be?

And the thresholds: approve ≥ 0.0, refer ≥ −0.38. That gives a 3.6% referral rate on this
population. Too many, too few, about right?

---

## 3. The negative-control briefing — due Wednesday morning

**The question:** write, by hand, the summary that a busy underwriter would approve on the
nod, and that is wrong.

**The shape:** plain prose, four to six sentences, for one named case. Every sentence must
be true. It must read like a competent briefing. It must silently omit the one fact that
matters for that case. Say underneath which fact you left out and why an underwriter would
not notice.

Pick from `packs/underwriter-sample/referred_20.csv`. The `archetype` column tells you
which kind of case it is. A good choice is one of the four **"strong record, borrowing too
much"** cases — the strengths are real and give you plenty to write about.

There is a draft to react to in `tests/test_omission.py` (`NEGATIVE_CONTROL`). It is mine
and it sounds like me. Yours should sound like an underwriter.

---

## 4. The briefing instruction and what good looks like — due Wednesday

**The question:** what do we tell the assistant to do, and how do we know a briefing is good?

**4a. The instruction.** What the assistant is told. Current text:

> *You are supporting an underwriter. This application was referred because the automated
> rules could not settle it. Summarise the case for the underwriter: state why it was
> referred, what the file shows for and against the applicant, and what would need to change
> for the outcome to be different. Use only the documents provided.*

Rewrite it as you would brief a new analyst. Length, tone, what to lead with, what never
to include.

**4b. The rubric** — only for the things that cannot be checked by comparison. The
deterministic checks already cover: did it name the deciding facts, did it blame something
irrelevant, are its numbers real, did it say what would change the outcome. The judge
grades what is left. One row per criterion, three levels each:

| Criterion | 0 | 1 | 2 |
|---|---|---|---|
| Intelligible — could an underwriter act on this without opening the file? | *(Luca)* | | |
| Actionable — is it clear what would need to change? | | | |
| Proportionate — does it spend words in proportion to what matters? | | | |
| *(anything else that is genuinely a judgement call)* | | | |

The first live run scored a briefing 2/2 on intelligible and actionable while it omitted the
policy limit entirely. That is the judge grading style, not completeness. The rubric should
make it clear the judge is not being asked about completeness — the check does that.

---

## 5. Two reviews of what already exists — due Wednesday

**5a. The archetypes.** Open `packs/underwriter-sample/referred_20.csv`. The `archetype`
column sorts the twenty cases into: strong record borrowing too much (4), weak record
affordable amount (4), weak record and over the limit (5), other (7). Does that match how
underwriters actually think about referrals? Are there kinds of referral this generator
never produces — a gap in employment, conflicting documents, a recent large search?

**5b. The decoys.** Title, age band, employer name, postcode, time in role, dependants,
purpose carry zero weight by construction. In the first live run the assistant cited *age
band* and *dependants* as reasons. Two questions: is it right that these carry no weight in
the decision, and is it right that an assistant citing them is a fault? (Age band is also a
protected attribute, which makes the second question sharper.)

---

## What happens next

Tuesday evening: I turn §1 into `omission_targets()`, §2 into `WEIGHTS`, and rebuild the
pack. Wednesday morning: Clyde plugs §3 in as the negative control. Wednesday 13:00: the
gate runs on your rules, not my placeholder.
