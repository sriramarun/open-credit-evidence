# Fine-tuning a Nemotron Nano judge — the plan

Owner: Sriram. Written 17 September 2026. Nothing in this document is built yet;
it describes the work in the order it has to happen.

## 1. What we are doing, in plain words

Today the judge is Nemotron 3 Ultra, a 550-billion-parameter model that runs on
NVIDIA's cloud. It reads an underwriter briefing and scores it for readability.
Two problems with that for a bank: the briefing has to leave the building to be
graded, and every grade costs a cloud call.

The plan is to teach a small model, Nemotron Nano, to grade the way Ultra does,
and run it on our own GPU. Ultra is the *teacher*: it grades a few hundred
briefings and we keep its answers. Nano is the *student*: we adjust it until it
gives the same answers on briefings it has not seen. This is called
*distillation*. The adjustment method is *LoRA*, which changes a small add-on to
the model rather than the whole model, so it trains in an afternoon on one GPU
and the result is a file of a few hundred megabytes.

Regulation text does not go into the model. It goes into a small search index
that hands the judge the relevant passage at grading time. Regulations change
(the Annex III date just moved to December 2027); a document is swapped, a model
is retrained.

## 2. The goal, stated precisely

**Input** to the judge, every time:

1. the briefing text;
2. the regulation passage retrieved for it (one or two paragraphs);
3. the rubric.

**Output**, always this JSON and nothing else:

```json
{"intelligible": 0, "actionable": 0, "overridable": 0,
 "citation": "AI Act Art 14(4)(a)", "reason": "one or two sentences"}
```

Scores are 0, 1 or 2. `citation` must be the passage the judge was given.

**Success** means, on 50 held-out briefings the student never saw:

| Measure | Target | Below this we do not ship |
|---|---|---|
| Exact score agreement with Ultra, per field | ≥ 85% | 70% |
| Agreement within one point | ≥ 95% | 90% |
| Citation matches the passage given | ≥ 98% | 95% |
| Luca agrees with the student on 20 blind cases | ≥ 16 of 20 | 14 |
| Improvement over the un-tuned Nano | must be positive | if not, we report that instead |

**Gate:** if these are not met by Friday 3 October, the final presentation uses
Ultra as the judge and shows the distillation as work in progress with whatever
numbers exist. The demo does not depend on this.

## 3. What has to exist before training can start

| Needed | Who | State on 17 Sep |
|---|---|---|
| Briefings at volume (300–500) from the runner, as transcripts | Clyde | runner not built; assistant server is up on the node, 2–3 s per call |
| Ultra labels for each briefing, in the JSON above | Sriram | adapter and rubric exist; regulation passage not yet included |
| Regulation corpus: ~40 passages, one file per document, one reason line each | Luca | not started |
| Rubric wording for `overridable` | Luca | `intelligible` and `actionable` exist |
| The NeMo container on the node | — | present: `nvcr.io/nvidia/nemo:26.08.00` |
| A Nano checkpoint on `/data/team08` | Sriram | not downloaded |

The first two are the gating ones. Everything in stages 0–2 below can be done
while waiting for them.

## 4. The stages

### Stage 0 — Environment (Thu 18 Sep, half a day)

Purpose: prove that training can run on the node at all before anything depends on it.

1. Get a GPU: `srun --gres=gpu:1 -n1 -p defq --time=04:00:00 --pty bash`.
2. Create the shared layout: `mkdir -p /data/team08/{models,judge-train,runs,corpus}`.
3. Start the NeMo container with `/data/team08` mounted and the proxy passed in,
   the same way `serve_lightning.sh` does for the NIM. Confirm `python -c "import nemo"`
   and `nvidia-smi` work inside it.
4. Run the smallest LoRA example NeMo ships, on any tiny model, for 10 steps.
   If it finishes, the toolchain works. If it does not, fall back to Hugging
   Face `peft` + `trl` in a plain venv — same result, plainer tooling.

Done when: a 10-step LoRA run completes on the node and writes a checkpoint to `/data/team08/runs/smoke/`.

### Stage 1 — Choose and fetch the student model (Thu 18 Sep, one hour)

Two candidates. Pick the one the Stage 0 toolchain supports out of the box.

| Model | Size | Notes |
|---|---|---|
| Nemotron 3 Nano 30B-A3B | 30B total, 3B active | Same family as Lightning; strong; heavier to train |
| Nemotron Nano 2 (9B or 12B) | dense | Smaller, simpler LoRA, faster to iterate |

Download from Hugging Face through the proxy into `/data/team08/models/<name>/`.
Record the exact revision hash — it goes in the run manifest. Check the licence
file in the download (NVIDIA Open Model License permits fine-tuning and
redistribution of the adapter).

Done when: the checkpoint is on `/data` and a one-question chat call against it
through vLLM returns text.

### Stage 2 — Freeze the task (Fri 19 Sep)

Purpose: the training data format cannot change once labelling starts.

1. Write the prompt template: rubric + passage + briefing, in that order. Save it
   as `specs/judge_prompt.md`; its hash is the `prompt_version`.
2. Luca supplies the `overridable` wording and the regulation corpus.
3. Build the retrieval index: chunk the corpus by article/paragraph, embed with
   `nemotron-3-embed-1b` (`input_type=passage`), store in Milvus Lite at
   `/data/team08/corpus/regs.db`. Retrieval returns the top-2 passages for a
   briefing.
4. Run five briefings through Ultra with the full prompt. Read the outputs with
   Luca. Adjust the rubric until both are satisfied. Then stop changing it.

Done when: `specs/judge_prompt.md` is committed and five Ultra outputs are in the
JSON format with sensible scores.

### Stage 3 — Build the label set (Mon 22 – Tue 23 Sep, depends on Clyde)

Purpose: 300–500 (briefing, passage, Ultra answer) examples.

1. Clyde's runner produces briefings for 400 referred applications against the
   node's Lightning server. Include the negative controls and 30–50 deliberately
   damaged briefings (a section deleted, a number changed) so the low scores are
   represented. Without these the student learns to say "2, 2, 2".
2. For each briefing: retrieve the passage, call Ultra, store one JSON line:

   ```json
   {"case_id": "APP000044", "briefing": "...", "passage": "...", "passage_id": "aia-art14-4a",
    "label": {"intelligible": 2, "actionable": 1, "overridable": 2,
              "citation": "AI Act Art 14(4)(a)", "reason": "..."},
    "teacher": "nvidia/nemotron-3-ultra-550b-a55b", "prompt_version": "ab12cd34"}
   ```

   Ultra at 40 requests per minute: 400 labels in about 20 minutes of wall time
   plus retries.
3. Split by *case*, not by briefing: 80% train, 10% validation, 10% test. A case
   appears in one split only. Save as `train.jsonl`, `val.jsonl`, `test.jsonl`
   under `/data/team08/judge-train/v1/`.
4. Luca reads 30 labels from the training split blind. If he disagrees with more
   than 5, the rubric is wrong; go back to Stage 2 before spending GPU time.

Done when: three files exist, the split is by case, and Luca has signed off the 30.

### Stage 4 — Baseline (Wed 24 Sep, two hours)

Purpose: know what the fine-tune has to beat.

Run the *un-tuned* Nano on `test.jsonl` with the exact prompt. Score it with the
Section 2 measures. Two possible outcomes:

- Agreement is already 80%+: the fine-tune is a small improvement and the
  presentation says so honestly. Still worth doing for the JSON format
  reliability, but expectations change.
- Agreement is low (typical for a 9B model on a strict JSON scoring task): the
  fine-tune has a clear job.

Done when: `runs/baseline/metrics.json` exists.

### Stage 5 — Train (Wed 24 – Thu 25 Sep)

Starting configuration, to be adjusted once:

| Setting | Value | Why |
|---|---|---|
| Method | LoRA | Adapter file, not a new model; swappable |
| Rank / alpha | 16 / 32 | Standard for format-and-scoring tasks |
| Target modules | attention and MLP projections | Both matter for following a rubric |
| Learning rate | 1e-4 | Conservative |
| Epochs | 3 | 400 examples; more overfits |
| Batch | 8 (gradient accumulation if memory bites) | — |
| Max sequence | 4096 tokens | Rubric + passage + briefing fits with room |
| Loss | On the JSON output only, not the prompt | We are teaching the answer, not the question |
| Seed | 7 | Recorded |

Each run writes to `/data/team08/runs/<date>-<name>/` with `config.yaml`, the
git hash of the repo, the data version, the adapter, and training loss per step.
Expect 1–2 hours per run on one GPU. Two or three runs is the budget.

Done when: validation loss has flattened and the adapter is saved.

### Stage 6 — Evaluate (Fri 26 Sep)

Run the student on `test.jsonl` — the cases nobody trained or tuned on.

1. Compute the Section 2 measures. Put them next to the baseline and next to
   Ultra-vs-Luca agreement from the Week 3 study.
2. Citation check: does every output cite the passage it was given?
3. Luca scores 20 held-out briefings blind; compare with the student.
4. Look at every disagreement. Sort them: rubric ambiguity, student error,
   teacher error. That table is the honest result, whichever way it goes.

Done when: `runs/<name>/eval.md` has the table and the disagreement list.

### Stage 7 — Serve on the node (Mon 29 Sep)

1. vLLM with `--enable-lora`, base model plus adapter, on one GPU, port 8001.
   If the NIM container supports adapter loading for this base, use that instead.
2. `curl` test from the login node, same as the assistant.
3. Two lines in `.env`: `EVIDENCE_JUDGE_BASE_URL=http://rtx-3se-05-36:8001/v1`,
   `EVIDENCE_JUDGE_MODEL=<served name>`. The framework then runs entirely on the
   node; every transcript records the endpoint.
4. Run the sample pack end to end with the student as judge.

Done when: the sample pack runs with no cloud call except embedding.

### Stage 8 — Record (Tue 30 Sep)

- Training run cited in the evidence pack the same way an evaluation run is:
  data version, config, seed, git hash, metrics.
- `docs/distillation.md` rewritten from "not now" to what was done and what the
  numbers are.
- Notebook `03_nano_judge.ipynb`: the story from label set to served model, with
  outputs, for the mentor.
- Gate decision written down: ship the student, or present Ultra and the numbers.

## 5. Timeline

| Week | Days | Stages | Depends on |
|---|---|---|---|
| 2 | Thu 18 – Wed 23 Sep | 0, 1, 2, 3 | Luca's corpus and rubric by Fri 19; Clyde's briefings by Mon 22 |
| 3 | Thu 24 – Wed 30 Sep | 4, 5, 6, 7, 8 | Stage 3 complete |
| 4 | Thu 1 – Fri 3 Oct | gate decision; rehearsal | — |

Stages 0–2 need nothing from anyone else and start on Thursday.

## 6. What can go wrong, and what we do

| Risk | Signal | Response |
|---|---|---|
| Clyde's runner is late | No briefings by Mon 22 | Sriram generates 200 with a 30-line script against the node; the runner catches up later |
| Labels are all high scores | Fewer than 20% of labels below 2 | Add more damaged briefings; re-label |
| NeMo container fights the proxy or the driver | Stage 0 fails | HF `peft` in a venv; same adapter format |
| Baseline is already good | Stage 4 ≥ 80% | Say so; ship the fine-tune for format reliability only |
| Student does not converge | Val loss flat and high after run 2 | Try the other candidate model; if still flat by 3 Oct, present Ultra |
| Node is busy | GPUs held by containers | Stop idle containers; training needs one GPU for two hours |
| The judge starts being used for completeness | Anyone proposes it | No. Completeness is the deterministic checks; the judge is Tier 2 (`docs/verifiers-law.md`) |

## 7. Words used above

| Word | Meaning here |
|---|---|
| Fine-tune | Continue training an existing model on our examples so it behaves the way we want |
| LoRA | A fine-tuning method that trains a small add-on (adapter) instead of the whole model |
| Adapter | The file LoRA produces; loaded on top of the base model at serving time |
| Distillation | Training a small model to reproduce a large model's answers |
| Teacher / student | Ultra / Nano |
| Held-out | Examples kept aside and never used in training, so the test is honest |
| Agreement | How often two graders give the same score |
| Milvus Lite | A small vector database that runs inside a Python process, no server |
| vLLM | The serving engine inside the NIM; can also be run directly with an adapter |
| Run manifest | The record of exactly what ran: model, data, config, seed, git hash |
