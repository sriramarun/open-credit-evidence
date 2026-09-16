# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
# ruff: noqa: E501  (markdown tables cannot wrap)
"""Generate notebooks/02_cluster_setup.ipynb. Edit this file, never the .ipynb.

    .venv/bin/python notebooks/build_cluster_setup.py
    .venv/bin/jupyter nbconvert --to notebook --execute --inplace \
        --ExecutePreprocessor.kernel_name=credit-evidence \
        --ExecutePreprocessor.timeout=900 notebooks/02_cluster_setup.ipynb

Executing needs the Codefest VPN up: the code cells talk to the team's GPU node.
"""

from __future__ import annotations

from pathlib import Path

import nbformat as nbf

OUT = Path(__file__).with_name("02_cluster_setup.ipynb")

nb = nbf.v4.new_notebook()
nb.metadata["kernelspec"] = {
    "name": "credit-evidence",
    "display_name": "credit-evidence (.venv)",
    "language": "python",
}
cells = nb.cells
md = lambda s: cells.append(nbf.v4.new_markdown_cell(s.strip()))  # noqa: E731
code = lambda s: cells.append(nbf.v4.new_code_cell(s.strip()))  # noqa: E731

md("""
# Running the assistant on our own GPUs

This notebook explains, from nothing, how we moved the assistant under test from
NVIDIA's cloud endpoint to the Codefest cluster, and how to check it is working.
Every step was done on 16 September 2026; the code cells at the end were run live
against the server and their outputs are saved here.

**Why bother?** Two reasons.

1. A bank will not send loan files to a cloud API. If the framework only works
   against NVIDIA Build, the demo is fine but the product is not. Running the same
   model on hardware we control is the on-premise story.
2. The free cloud endpoint took between 8 and 150 seconds per call and was shared
   with everyone else at the event. Our own server answers in about 2 seconds.

## Words you will meet

| Word | Plain meaning |
|---|---|
| **Cluster** | A set of computers in a data centre that you use over the network. Ours has one *login node* (a small machine with no GPUs, where you arrive) and *GPU nodes* (big machines with 8 GPUs each, where work runs). |
| **VPN** | A private tunnel from your laptop into the cluster's network. Without it, the cluster's addresses do not exist as far as your laptop is concerned. |
| **SLURM** | The queue manager. Nobody runs on a GPU node directly; you ask SLURM for a GPU, it gives you one and tells you which. |
| **Docker / container** | A packaged application with everything it needs inside. You download the package once (the *image*) and run it (a *container*). |
| **NIM** | NVIDIA's ready-made container for serving a model. Start it, and it downloads the model weights and exposes an API that looks exactly like OpenAI's. Our code cannot tell the difference between a NIM and the cloud. |
| **Weights** | The model itself — about 60 GB of numbers for Nemotron 3.5 Lightning. |
| **Endpoint** | A web address that answers model requests, e.g. `http://rtx-3se-05-36:8000/v1`. |
| **Proxy** | The cluster does not let machines talk to the internet directly; traffic goes through a proxy server. This matters twice below. |
""")

md("""
## Step 1 — Get in

You need three things from the organisers: the VPN profile (`codefest.ovpn`), a
username, and a password. Sriram's username is `team08_user3`.

1. Install the AWS VPN Client and add the `.ovpn` profile. Connect. Only cluster
   traffic goes through the tunnel; the rest of your laptop is unaffected.
2. Test: `ssh team08_user3@10.130.232.14`. You land on the login node.

**Make it painless.** Typing a password every time gets old, and a script cannot
type it for you. Create a key once and copy it up (this asks for the password one
last time):

```bash
ssh-keygen -t ed25519 -f ~/.ssh/codefest -N "" -C "sriram-codefest"
ssh-copy-id -i ~/.ssh/codefest.pub team08_user3@10.130.232.14
```

Then add a shortcut to `~/.ssh/config`:

```
Host codefest
  HostName 10.130.232.14
  User team08_user3
  IdentityFile ~/.ssh/codefest
  ServerAliveInterval 30
```

From now on `ssh codefest` just works.
""")

md("""
## Step 2 — Ask SLURM for a GPU

The login node has no GPUs and no docker. You must ask for a GPU node:

```bash
srun --gres=gpu:1 -n1 -p defq --time=08:00:00 --pty bash
```

Reading that left to right: *give me 1 GPU, 1 task, from the `defq` partition,
for up to 8 hours, and open an interactive shell there.* Your prompt changes to
`team08_user3@rtx-3se-05-36:~$` — you are now on the GPU node.

Useful to know:

- `echo $CUDA_VISIBLE_DEVICES` prints the number of the GPU SLURM gave you. **Use
  that number**, never assume GPU 0.
- `nvidia-smi` shows all 8 GPUs and what is using them.
- `exit` takes you back to the login node and releases the GPU.
- Each team gets one node. Ours is `rtx-3se-05-36`.
- One gotcha: `ssh codefest 'srun ...'` fails with *command not found* because
  non-interactive shells skip the file that sets up SLURM. Use
  `ssh -t codefest 'bash -lc "srun ..."'` from a script, or just log in first.
""")

md("""
## Step 3 — Save your NGC key

The NIM downloads weights from NVIDIA's registry (NGC) and needs your key for that.
Do **not** type it on the command line as `export NGC_API_KEY=...` — everything you
type is saved in `~/.bash_history` in plain text. Put it in a file only you can read:

```bash
umask 077
echo "export NGC_API_KEY=nvapi-YOUR-KEY" > ~/.ngc_key
```

`umask 077` means "files I create now are private to me". Later, `source ~/.ngc_key`
loads it into the current shell without it appearing in history.
""")

md("""
## Step 4 — Start the server

On the GPU node:

```bash
source ~/.ngc_key
bash ~/open-credit-evidence/scripts/cluster/serve_lightning.sh
```

The script is in the repo. What it does, line by line, because each line fixes a
problem we actually hit:

| Line | Why |
|---|---|
| `module load docker` | Docker is not on the path until you load it. |
| `--gpus "device=$CUDA_VISIBLE_DEVICES"` | Use the GPU SLURM assigned. The obvious `--gpus 1` grabs GPU 0 — which may be somebody else's. |
| `-v /data/team08/nim-cache:/opt/nim/.cache` | Keep the 60 GB of weights on the team's shared disk, downloaded once for all four accounts. The first teammate to run this used their private home directory, so nobody else could reuse it. |
| `-e HTTP_PROXY=... -e HTTPS_PROXY=...` | The container must be told about the proxy or it cannot reach NGC to download. |
| `--network host` | The container's port 8000 is the node's port 8000. |
| `curl --noproxy '*' http://127.0.0.1:8000/...` | Talking *to* the container must bypass the proxy, otherwise the request goes out to the proxy and never comes back. |
| the health loop | Waits until the model is loaded, then prints the two lines to put in `.env`. |

First start downloads the weights — allow 10–20 minutes. Ours reported `ready` in
under two minutes, which suggests this NIM image ships with the weights inside it.
Either way, the second start is instant.

The container keeps running after you `exit` the SLURM session. It also keeps its
GPU. To stop it, on the node: `docker stop nemotron-lightning`.
""")

md("""
## Step 5 — Test it from the cluster

Simplest possible test, from the login node or the GPU node:

```bash
bash ~/open-credit-evidence/scripts/cluster/check_endpoint.sh http://rtx-3se-05-36:8000/v1
```

Or the raw request, so you can see there is no magic:

```bash
curl -s --noproxy '*' http://rtx-3se-05-36:8000/v1/chat/completions \\
  -H 'Content-Type: application/json' \\
  -d '{"model":"nvidia/nemotron-3.5-lightning","temperature":0,"max_tokens":60,
       "chat_template_kwargs":{"enable_thinking":false},
       "messages":[{"role":"user","content":"What is a debt-to-income ratio?"}]}'
```

Two details:

- The model is called `nvidia/nemotron-3.5-lightning` on our server but
  `nvidia/nemotron-3.5-lightning-30b-a3b` on NVIDIA Build. Same model, different
  label. That is why the `.env` needs both the URL and the name.
- Use `/v1/chat/completions`, not `/v1/completions`. The plain completions endpoint
  leaks the model's private reasoning (`</think>`) into the answer.
""")

md("""
## Step 6 — Test it from your laptop, through our own code

The cells below ran on Sriram's laptop with the VPN connected. The node is reachable
directly, so the whole framework runs from here against the on-prem model.

Pointing a role at a different server is two environment variables. Nothing else
in the code changes; every response records where it came from.
""")

code("""
import os
import socket

NODE_IP, PORT = "10.130.232.20", 8000  # rtx-3se-05-36

os.environ["EVIDENCE_ASSISTANT_BASE_URL"] = f"http://{NODE_IP}:{PORT}/v1"
os.environ["EVIDENCE_ASSISTANT_MODEL"] = "nvidia/nemotron-3.5-lightning"

with socket.create_connection((NODE_IP, PORT), timeout=3):
    print(f"VPN is up: {NODE_IP}:{PORT} answers")
""")

code("""
from evidence.adapters.nvidia_build import chat, endpoint_for

for role in ("assistant", "judge", "embed"):
    ep = endpoint_for(role)
    where = "NVIDIA Build" if ep.is_build else "on-prem"
    print(f"{role:9} -> {where:12} {ep.base_url}  {ep.model_id}")
""")

md("""
Only the assistant moved. The judge (550B) stays in the cloud — it would need the
whole node to itself — and the embedder makes too few calls to matter yet.

Now one call, the simplest possible:
""")

code("""
r = chat("assistant", system="Answer in one sentence.", user="What is a debt-to-income ratio?",
         max_tokens=60, thinking=False)
print(f"endpoint : {r.endpoint}")
print(f"model    : {r.model_id}")
print(f"took     : {r.latency_ms / 1000:.1f} s   tokens in={r.tokens_in} out={r.tokens_out}")
print(f"answer   : {r.text.strip()}")
""")

md("""
## Step 7 — A real case, five times

Speed is nice, but the reason we wanted our own server was *reproducibility*: with
temperature 0 and a fixed seed, does the model give the same briefing every time?
On the shared cloud endpoint it did not. Here is the same referred application,
APP000044, run five times.
""")

code("""
import hashlib
import re
from pathlib import Path

from evidence.checks import run_checks
from evidence.contracts.item import BenchmarkItem

PACK = Path("../packs/underwriter-sample")
items = [BenchmarkItem.model_validate_json(line) for line in (PACK / "items.jsonl").open()]
item = next(i for i in items if "APP000044" in i.item_id)
case = "\\n\\n".join(d.content for d in item.context)

print("what the marking key says must be stated:")
for ref in item.grading.omission_refs:
    print("  -", item.grading.omission_labels[ref])
print()

runs = []
print(f"{'run':>3} {'secs':>5} {'fingerprint':>12} {'omission':>9} {'audit':>5}  "
      "ratio stated   cites 'age band'")
for n in range(1, 6):
    r = chat("assistant", system=item.prompt, user=case, max_tokens=700)
    (chk,) = run_checks(["material_omission"], output=r.text, item=item)
    pcts = sorted(set(re.findall(r"\\d+(?:\\.\\d+)?%", r.text)) - {"40%"})
    runs.append(r.text)
    print(f"{n:>3} {r.latency_ms / 1000:>5.1f} {hashlib.sha256(r.text.encode()).hexdigest()[:12]} "
          f"{'PASS' if chk.passed else 'FAIL':>9} {str(chk.needs_audit):>5}  {', '.join(pcts):14} "
          f"{'age band' in r.text.lower()}")

print(f"\\nidentical outputs: {len(set(runs))} distinct out of {len(runs)}")
""")

md("""
And the arithmetic the model was supposed to do, done by hand:
""")

code("""
income = 15_922
existing, instalment = 316, 314
monthly_income = income / 12
ratio = (existing + instalment) / monthly_income
print(f"£{existing} + £{instalment} = £{existing + instalment} per month")
print(f"£{income} / 12 = £{monthly_income:,.2f} per month")
print(f"ratio = {ratio:.1%}   (policy limit 40%)")
""")

md("""
One of the five briefings, so you can see what the underwriter would actually read:
""")

code("""
print(runs[0].strip())
""")

md("""
## What this showed

**1. The server works and is fast.** Two to three seconds per briefing, from a
laptop, through the same code that talks to the cloud. The transcript records
`endpoint=http://10.130.232.20:8000/v1`, so the evidence pack can say the run was
on-premise.

**2. The model's arithmetic is unreliable, and the briefing hides it.** The
correct ratio is 47.5%. Look at the *ratio stated* column: in this execution three
of five briefings gave a wrong figure (about 41.5%) and two gave the right one. An
hour earlier, five runs gave 44.7%, 42.6%, 43.6%, 39.6% and 43.5% — none right, and
one *below* the limit it then said was breached. Every briefing passes
`material_omission`, because each one does state that the 40% limit is exceeded,
which is the fact we asked for. The check is blind to the number being wrong. That
is what `numeric_fidelity` is for — compare every number in the briefing against the
case file — and this result moves it to the top of the Week 2 list.

**3. Our own server is not byte-for-byte reproducible either.** Same prompt, same
seed, temperature 0, five different fingerprints. This is how vLLM serves large
mixture-of-experts models: requests are batched together and the arithmetic comes
out slightly differently depending on what else is in the batch. It cannot be
configured away. So the framework's reproducibility claim must be *same verdict
across N runs, N recorded* — not *same text*. The runner will make three passes per
item and report agreement; an item whose verdict flips between passes is itself a
finding.

**4. The decoy problem is still there.** Most briefings list the applicant's age
band as a point against them (last column). It has no weight in the decision and
is a protected characteristic. `decoy_citation` catches this; it is the second
check to port.
""")

md("""
## If something goes wrong

| Symptom | Likely cause | Fix |
|---|---|---|
| `srun: command not found` | Non-interactive shell | Log in first, or `ssh -t codefest 'bash -lc "srun ..."'` |
| `srun` sits at *queued and waiting* | Team's node is full, or you asked for a node that is not ours | `squeue --me` to see; `scancel <id>`; drop the `-w` flag |
| `docker: permission denied ... docker.sock` | You are on the login node | Docker only exists on GPU nodes |
| `NGC_API_KEY is not set` | Forgot `source ~/.ngc_key` | Run it in the same shell as the script |
| `curl` hangs against `127.0.0.1` | Went through the proxy | Add `--noproxy '*'` |
| Health check never says ready | Still downloading, or a crash | `docker logs -f nemotron-lightning` |
| Laptop cannot reach `10.130.232.20` | VPN not connected | Connect the AWS VPN Client |
""")

nb.metadata["language_info"] = {"name": "python"}
OUT.write_text(nbf.writes(nb))
print(f"wrote {OUT}")
