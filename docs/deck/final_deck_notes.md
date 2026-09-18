# Final deck — speaker notes (draft, 18 Sep)

Ten minutes. Slides 6, 7 and 9 carry mockup numbers marked with a yellow tag;
they are replaced by real results after the full run (target 30 Sep) and the
judge study (3 Oct). Slides 2, 4 and 8 use real numbers from 13–16 Sep.

| # | Slide | Time | What to say |
|---|---|---|---|
| 1 | Title | 0:00–0:20 | Name, three people, mentor. One sentence: we produce evidence that an AI assistant told the human what mattered — computed, not judged. |
| 2 | The problem | 0:20–1:30 | Read the quote. The ratio is 41.58%; the file says 47.5%. Ultra gave it 2/2. Ten runs, eight wrong, six cited age band. Then the sentence that matters: a model cannot tell you what another model got wrong. Annex III 5(b): this is high-risk; the deployer must be able to show oversight worked. |
| 3 | Why different | 1:30–2:30 | Verifier's Law in one line. Then walk one row of the table: where the right answer comes from. Everything else follows from that row. Do not read the whole table. |
| 4 | Ground truth by construction | 2:30–3:30 | Left to right: hidden tier → observables and decoys → scorecard → sealed key. The r ≈ −0.04 box: decoys are independent by measurement, not by assertion. The 0 box: the hidden tier does not leak; there is a test for it. |
| 5 | How it works | 3:30–4:15 | Six boxes, one breath each. Point at the green one: this is the thing under test. Point at box 5: the judge grades readability and nothing else. Name the four models and where each runs. |
| 6 | Live run | 4:15–6:00 | Switch to the terminal on the node. Run the command. While it runs (about two minutes): every row is a check, every number traces to a transcript. When the table appears, read the numeric_fidelity row aloud and the repeat-agreement row. |
| 7 | Evidence pack + tamper | 6:00–7:00 | Open report.md. Article 15, Article 14, then the two lines that matter to a supervisor: CONTRIBUTES and NOT COVERED — we say what we do not do. Run verify: OK. Change one digit. Run verify: FAIL, names the file. |
| 8 | What we found | 7:00–7:45 | Four numbers, real, from 16 Sep. The retrieval failure and what the transcript let us attribute. No single check is enough. |
| 9 | On-prem and the judge | 7:45–8:45 | Left: same pack, cloud on 15 Sep, our node on 7 Oct, two lines of config. Right: the agreement table — why we distilled (data cannot leave), why regulations are retrieved not trained (the Annex III date moved this year). Last bullet again: the judge never grades correctness. |
| 10 | Day 1 to Day 5 | 8:45–9:15 | Left column is what existed on 9 Sep: a proposal. Right column is today. Everything in between is dated in the repo. |
| 11 | Who uses it | 9:15–9:45 | The reader is a supervisor — public sector. Public lenders run the same pattern. Apache 2.0; a new domain is a new spec; regulations change without retraining. The strip: what we do not claim. |
| 12 | Close | 9:45–10:00 | Evidence, not opinion. Repo URL. Stop. |

## Questions we expect, and the answers

- **Why not just use a bigger judge?** Ultra is 550B and gave full marks to a fabricated ratio. Size does not fix the category error: a model grading a model is an opinion. Our checks are comparisons against a computed answer.
- **Your data is synthetic — does this transfer to real loans?** The framework evaluates the assistant's behaviour on cases where the truth is known. Real files have no marking key, so no check is possible on them. Synthetic cases are the only way to get ground truth by construction; the recipe is a YAML spec a bank can rewrite for its own scorecard.
- **Why Nemotron for both assistant and judge — self-preference?** The judge never grades correctness, so self-preference cannot affect the evidence. For readability, the student is calibrated against a human. If asked further: a non-NVIDIA judge would be a one-line config change and we would welcome the comparison.
- **What about fairness?** Not claimed. Decoy citation catches a briefing that cites a protected characteristic; population-level fairness needs data and a definition the bank owns. It is on the NOT COVERED line.
- **Public sector?** Supervisors read the pack; public lenders and guarantee schemes run the same assistants; Annex III 5(b) does not say "bank".
- **Is the fine-tune necessary?** It makes the judge affordable and on-prem. If the numbers had not beaten the un-tuned baseline we would have said so — the baseline row is on the slide for that reason.

## Rehearsal checklist

- VPN up, node reachable, Lightning NIM answering, Nano judge answering, before walking in.
- `evidence run` timed at under 2 minutes on the node; if slower, use `--repeats 1` and say so.
- The recording of slides 6–7 from the last rehearsal on the laptop, in case the network fails.
- Every yellow "mockup" tag removed before 7 Oct.
