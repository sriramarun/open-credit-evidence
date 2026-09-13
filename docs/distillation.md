# Model distillation — feasibility check

The mentor asked us to look at it. One afternoon, as the plan says. Answer below.

## What it would mean here

Distillation trains a small model to reproduce a large model's behaviour. Two
places it could apply:

1. **Distil the judge.** Use Nemotron 3 Ultra's grading decisions as labels and
   train Nemotron 3 Nano to reproduce them, so judging is cheap enough to run
   continuously.
2. **Distil the assistant.** Train a small model to write briefings the way Super
   does, so a bank could deploy it on its own hardware.

## Is it worth doing in these four weeks

**No.**

- Neither version is on the path to the 7 October demo. The demo is the omission
  catch, the evidence pack and the tamper test. A distilled model changes none of
  those.
- It is a week of work minimum: a training pipeline, GPU time, and then an
  evaluation of the distilled model — which is a second instance of the exact
  problem we are building the framework to solve. We would be evaluating our own
  distillate before we have finished the evaluator.
- The judge version needs labelled data we do not have yet. The agreement study in
  Week 3 produces the first twenty labels. That is not a training set.
- Three people, and one of them is presenting.

## When it becomes worth doing

After the Codefest, the judge version is the interesting one. Once the agreement
study exists at scale, distilling the judge into Nano turns a per-call cost into a
fixed one, which is what makes continuous assessment — the SR 26-2 demonstrable-
evidence standard — affordable. It also gives the framework a second NVIDIA-shaped
story: the evaluator itself runs on a small open model.

## What we say to the mentor

We looked, we can see where it fits, and it is the first thing we would do after the
event. Building it now would cost the demo.
