# 4-Week Plan — Credit Evidence Engine

For the three of us to agree on. The detailed technical spec lives in `BUILD.md`;
this is the schedule and who does what.

- **Week 1 starts:** Thursday 10 September 2026
- **Final presentation:** Wednesday 7 October, 15:00–17:30
- **Codefest days (Wednesdays):** 16 Sep · 23 Sep · 30 Sep · 7 Oct
- **Team:** Sriram (credit data and models) · Clyde (backend) · Luca (economics and regulation)

---

## What we are building

An AI assistant reads a loan application that the bank's rules could not decide, and writes a
summary for the human underwriter who has to decide it. We test that assistant, and we produce
the evidence a bank's risk department needs to approve it for use.

**The one thing we must get right:** a summary can be completely accurate and still be
dangerous, because of what it leaves out. We catch that. Nobody else can, because catching it
means knowing in advance what should have been said — which means we have to invent the loan
applications ourselves.

**On 7 October we show:**

1. A summary that reads perfectly, leaves out the one fact the decision turned on, and gets
   failed by name — with no AI involved in that judgement.
2. An evidence report where every number can be traced back to the file that produced it.
3. That report being rejected when we change a single digit in it by hand.

---

## What the mentor told us on Day 1

| What they said | What we do |
|---|---|
| Design the system before coding — models, retrieval, safety | Clyde writes a two-page design note in Week 1, before engine code |
| Start small: one goal, one simple test, real data, working end to end | The Week 1 target is twenty cases running all the way through, not a finished component |
| Use RAG | The assistant searches the case file for what it needs rather than being handed everything at once. This is now the design. |
| Use NVIDIA Build, Nemotron, and their RAG blueprints | Hosted endpoints with the Codefest credits. **Settles the hosting question — we are not running our own models.** Start from their blueprint, don't write our own. |
| Do you need a domain-specific judge? | Open. Sriram and Luca decide by 23 Sep. |
| Look at model distillation | One afternoon of checking, answer yes or no on 23 Sep. Almost certainly a later thing. |
| Next week: find the models, pick the assistant model, pick the judge model | Sriram, by Friday |
| Register on openhackathon.org, get the credits working | **Today. Everything model-related is blocked behind it.** |

---

## Who does what

**Sriram — the cases and the marking**
Invents the loan applications, decides what counts as a fact that mattered versus a fact that
looks important and isn't, and writes the code that marks the assistant's answers. Picks which
models we use.

**Clyde — everything that runs**
The repository, the pipeline that puts each case to the assistant, the RAG search, the storage
that keeps every file with a fingerprint, the evidence report, the checker that re-verifies it,
and getting it running on OpenShift.

**Luca — what "correct" means, and the story**
Decides what a summary must contain for an underwriter to be properly informed — which is a
lending judgement, not a coding one. Writes the regulatory mapping and the honest statement of
what we don't test. Owns the ten-minute presentation.

### Three handovers to watch

**Luca → Sriram.** Sriram cannot write the omission check until Luca has said what must be in a
summary. This is the first thing due, on Friday.

**Sriram → Clyde.** They share two file formats: what a test case looks like, and what a marking
result looks like. Agree both by Friday and don't change them without telling each other.

**Nobody waits.** Clyde builds against a few hand-written fake cases. Sriram tests the marking
against hand-written fake answers. Real integration happens on the Wednesday.

---

## Week 1 — Thu 10 → Wed 16 Sep

**Target: twenty cases go all the way through, and we catch a summary that leaves something out.**

**Everyone, today.** Register on openhackathon.org, confirm the credits work, make one
successful call to a Nemotron model.

**Sriram**
- Pick the assistant model, the judge model, and the search model. Three lines on why for each.
- Check whether model distillation is worth doing later. One afternoon, no more.
- Write the recipe that generates loan applications — what fields exist, which hidden factor
  drives the outcome, and which fields deliberately have no effect at all.
- Generate twenty referred applications and turn them into documents: an application form and a
  credit bureau report.
- Write the omission check — does the summary mention every fact the decision turned on?

**Clyde**
- Two-page system design note. Models, search, safety, how data flows.
- Set up the repository: licence, notices, automated testing.
- Agree the two file formats with Sriram and lock them Friday.
- Get RAG working end to end on one case file. Quality doesn't matter yet, the pipeline does.
- Build the loader that reads test cases and refuses anything that has been tampered with.
- Build the runner that puts each case to the assistant and records exactly what was said.

**Luca**
- **Define what a summary must contain.** For a referred credit case, what does an underwriter
  need to be told? Sriram is blocked until this exists.
- Sanity-check the scoring: are the factors, the 40% affordability limit and the irrelevant
  fields plausible to someone who knows lending? Say so now, not in week four.
- Write the instruction we give the assistant, and what a good answer looks like.
- **Write the deliberately bad summary by hand** — fluent, every word true, quietly missing the
  one fact that matters. Clyde plugs it in as a fake assistant. This is the demo.

**Wednesday 16 Sep.** Twenty cases run and marked. The deliberately bad summary fails the
omission check and nothing else. We can point at the summary, at the missing fact, and at the
line of output that caught it.

*If behind: skip RAG this week and hand the assistant the whole file instead. Do not skip the
deliberately bad summary.*

---

## Week 2 — Thu 17 → Wed 23 Sep

**Target: a real assistant, a real set of cases, and results we can read.**

**Sriram**
- Build the real assistant: RAG over the case file, the briefing instruction, a Nemotron model.
- Write the other three checks — did it name the factors that mattered, did it blame something
  irrelevant, are its numbers real.
- Grow the case set to sixty or eighty, weighted towards the genuinely difficult ones.

**Clyde**
- Run all the checks over all the answers and record the results.
- Add the results up — grouped by regulation first, then by how hard the case was.
- Build the single command that runs the whole thing.
- Wire in the judge model for the parts a comparison can't settle.
- Put the engine in a container and get one deployment onto OpenShift.

**Luca**
- Write the regulatory mapping: which EU AI Act articles our evidence answers, which it only
  contributes to, and which it doesn't touch at all — with a reason for each.
- Decide with Sriram whether the judge needs credit-specific knowledge.
- First draft of the ten-minute script, so we build towards it.

**Wednesday 23 Sep.** The whole case set run against the real assistant, unattended, from one
command. Results broken down by difficulty. We can say what the assistant is good and bad at and
show why. Distillation decision announced.

*If behind: drop the judge to week three, or drop it and say so on stage. Do not drop the
results tallying — the evidence report can't be built without it.*

---

## Week 3 — Thu 24 → Wed 30 Sep

**Target: the evidence report, and the tamper test working. This is the week the demo is won.**

**Clyde — heaviest week, expect help**
- Build the evidence report, organised regulation by regulation. Every number in it is a link to
  the file that produced it. **No number is ever typed by hand.**
- Build the checker that re-reads every file, recalculates every number, and refuses the report
  if a single one no longer adds up.
- Sign the report, and add a block naming the person who stands behind it. A signature proves
  nothing has been altered; it is not a professional opinion, and the wording must not suggest it is.

**Sriram**
- The safety check. The mentor called safety out specifically: hide an instruction inside a bank
  statement and confirm the assistant does not follow it.
- Agreement study: twenty summaries, Luca and Sriram mark them independently, report how often
  they agree with each other and how often the judge agrees with them. A spreadsheet is fine.

**Luca**
- Write what this doesn't test — before we see the results. That order is what makes it credible.
- Settle who signs the report, over what scope.
- Second draft of the script, now against real numbers.

**Wednesday 30 Sep.** The checker passes on a clean report. We change one digit by hand and it
fails, naming the number. A full week before we need it.

*If behind: cut the agreement study and leave the judge's results out of the report. Never cut
the checker.*

---

## Week 4 — Thu 1 → Wed 7 Oct

**Target: prove it repeats, publish it, rehearse it. Code freeze Monday 5 October.**

- Run the whole thing twice from the same inputs and publish the comparison — they should differ
  only in timestamps. *(Clyde)*
- Fresh copy of the repository, one command, everything runs. *(Clyde)*
- Publish under Apache 2.0: the engine, the tests, one complete set of cases, and the recipe that
  generated them. *(Sriram and Clyde)*
- Write the runbook and the statement of what we claim. *(Luca and Clyde)*
- Two timed rehearsals — one to a mentor midweek, one internal on Monday. Record a backup video
  in case the cluster misbehaves. *(Luca leads)*

### The ten minutes, in order
1. The problem — a summary that is accurate, incomplete and dangerous.
   Then one line of framing: Verifier's Law — automate what is easy to verify; our checks are the verifier (`docs/verifiers-law.md`).
2. One command. It runs.
3. The catch — the missing fact, named.
4. The evidence report, organised by regulation, every number traceable.
5. The tamper test — change a digit, the report is rejected.
6. Two identical runs, one comparison.
7. Apache 2.0, here is the repository.

---

## What we are not building

| Not doing | Why |
|---|---|
| **The second use case (loan book monitoring)** | The biggest single piece of work. Without it we can say the design supports a second use case but not prove it. The most painful cut, and the first thing to add back if we find time. |
| **The "ceiling" measurement** | Depends on the second use case, and doesn't apply to a written summary anyway. |
| **Two more checks** — is "what would change this" correct, did it spot contradicting documents | Each needs new case-generation work as well as marking code. Five checks make the argument. |
| **Fairness and consistency pairs** | Genuinely valuable and genuinely a week. Say the cases are built for it and the analysis is next. |
| **Model distillation** | Interesting, off the critical path. |
| **A second assistant to compare against** | One assistant plus the deliberately bad one is enough to show the instrument works. |
| **Comparing one assessment to the next over time** | Explain the idea, don't build it. |
| **The Nemotron orchestration agent** | The single command is the reproducible path and the better thing to demonstrate. Add it back only if week three finishes early. |
| **Running our own models** | NVIDIA's hosted endpoints replace this. |

**If we have to cut more, in this order:** the judge and agreement study, then the safety check,
then the irrelevant-factor check, then the OpenShift deployment. The omission check, the evidence
report and the checker are not on this list.

---

## Decisions

| Decision | Who | By |
|---|---|---|
| Confirm the NVIDIA credits work end to end | Clyde | Today |
| Which assistant model, judge model, search model | Sriram | Fri 11 Sep |
| Copyright line — Algoritmica alone or both organisations | Luca | Fri 11 Sep |
| What a summary must contain, signed off | Luca | Fri 11 Sep |
| What we publish openly. Proposal: engine, tests, one case set, the recipe | Luca | Wed 16 Sep |
| Does the judge need credit-specific knowledge | Sriram + Luca | Wed 23 Sep |
| Distillation, in or out | Sriram | Wed 23 Sep |
| Who signs the evidence report | Luca | Wed 30 Sep |

---

## What could go wrong

**The evidence report is a week-three problem and it is the product.** Only Clyde can really do
most of it and it doesn't compress. If we're behind entering week three, cut from week two.

**Luca is on the critical path in week one and may not realise it.** The omission check can't be
written until he's said what a summary must contain. Friday, not "sometime".

**RAG introduces a failure we don't control.** If the search misses the paragraph containing the
affordability ratio, the assistant leaves it out for a reason that has nothing to do with the
model. Worth knowing, worth reporting — but we have to be able to tell the two apart, so record
what the search returned for every case from day one.

**One use case looks like a tool, not a framework.** Someone will ask. Straight answer: the
marking code contains nothing specific to credit, the boundary is real, and the second use case
is next. Don't overclaim it.

**"Your cases are made up."** Every time. Testing against a known answer is normal practice in
model validation; our results describe our cases and we say so in writing; and the finding only
points one way — **failing proves there's a problem, passing doesn't prove there isn't.**

**The omission check might be too generous.** A summary can convey a fact without naming it, so
we have to accept near-matches, and near-matches are where a sceptic attacks. Count them and
report the count. If someone finds loose matching hidden behind a strict-sounding check, they
stop trusting everything.

---

## Weekly rhythm

- **Wednesday 10:00–11:00** — Codefest scrum, four minutes. Prepare it Tuesday evening.
- **Wednesday 11:00–12:00** — mentor session. Bring one specific blocker, not a status update.
- **Wednesday 13:00–17:00** — all three of us integrate and run the whole thing together.
- **Thursday** — plan the week against this document.
- **Friday** — the riskiest thing of the week, while there's still time to recover.

**One rule:** if it hasn't run end to end by Wednesday afternoon, it isn't done — whatever the
tests say.
