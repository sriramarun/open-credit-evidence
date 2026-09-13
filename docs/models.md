# Model selection

The mentor's Week 1 homework: pick the assistant model, the judge model and the
embedding model, with three lines on why for each. All served from NVIDIA Build
using the Codefest credits — we run nothing ourselves.

**Status:** proposed. Confirm each is actually on the endpoint catalogue we have
credits for before Friday; the family is right, the exact checkpoint ids may not be.

## Assistant under test — Nemotron 3 Super

- 120B total parameters, 12B active. Cheap enough per call that we can run the full
  pack many times in a Codefest afternoon, which matters more than peak quality for
  an instrument we are calibrating.
- Built for agentic use, and the assistant is exactly that shape: retrieve from the
  case file, reason over it, produce a structured briefing.
- It is the model a bank would plausibly deploy for this job. Testing something
  nobody would deploy proves nothing.

## Judge — Nemotron 3 Ultra

- **Must not be the model under test.** A model grading its own output is the first
  objection a validator raises, and it is a free objection to remove.
- 550B mixture-of-experts reasoning model. A larger model judging a smaller one is
  the defensible direction; the reverse invites "the judge is worse than the thing
  it grades".
- Same family as the assistant, which keeps the whole stack on Nemotron for the
  event without compromising independence — different weights, different scale,
  different training run.

The judge grades only what exact comparison cannot reach: whether the briefing is
intelligible to an underwriter and whether the underwriter can tell what would need
to change. Everything else is a deterministic check. The judge ships with its
agreement study or it does not ship.

## Embedding model — for retrieval over the case file

- Candidate: NVIDIA's retrieval embedding on Build (the `nv-embedqa` line). Confirm
  the current id on the catalogue.
- The case file is two short documents. Retrieval is not a hard problem here; the
  point of RAG is that the assistant *selects* what to read rather than being handed
  everything, because that is how it fails in production.
- Log what was retrieved for every item from day one. If retrieval drops the
  paragraph with the debt-service ratio, the assistant omits it for a reason that
  has nothing to do with the model, and we have to be able to tell the two apart.

## What this is not

Not a model comparison. One assistant, one judge, one embedder. A second assistant
for comparison is on the add-back list and not before Week 3.
