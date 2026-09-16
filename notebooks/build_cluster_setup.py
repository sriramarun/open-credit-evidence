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
## Step 5 — Is it running?

Three questions, in order. Ask them on the GPU node (the container is only visible
from there).

**1. Is the container up?**

```bash
module load docker
docker ps --filter name=nemotron-lightning
```

You want to see one line with `Up 3 hours` or similar. If the list is empty, it is
not running — go to Step 6.

**2. Has the model finished loading?** A container can be *up* for minutes before
the model is ready to answer.

```bash
curl -s --noproxy '*' http://127.0.0.1:8000/v1/health/ready
```

`{"object":"health.response","message":"ready","status":"ready"}` means yes. Nothing, or
a connection refused, means it is still loading: `docker logs -f nemotron-lightning`
shows progress (Ctrl-C to stop watching; the container keeps running).

**3. Which model is it serving?**

```bash
curl -s --noproxy '*' http://127.0.0.1:8000/v1/models
```

Look for `"id":"nvidia/nemotron-3.5-lightning"`. Note the name: on NVIDIA Build the
same model is called `nvidia/nemotron-3.5-lightning-30b-a3b`. That is why `.env`
needs both the URL and the name.

**Then the first real test** — one question, one answer. This works from the login
node too, because it uses the node's name instead of `127.0.0.1`:

```bash
bash ~/open-credit-evidence/scripts/cluster/check_endpoint.sh http://rtx-3se-05-36:8000/v1
```

Expected: `nvidia/nemotron-3.5-lightning | A debt-to-income ratio (DTI) is ...`.

The same thing without the script, so you can see there is no magic:

```bash
curl -s --noproxy '*' http://rtx-3se-05-36:8000/v1/chat/completions \\
  -H 'Content-Type: application/json' \\
  -d '{"model":"nvidia/nemotron-3.5-lightning","temperature":0,"max_tokens":60,
       "chat_template_kwargs":{"enable_thinking":false},
       "messages":[{"role":"user","content":"What is a debt-to-income ratio?"}]}'
```

Use `/v1/chat/completions`, not `/v1/completions`. The plain completions endpoint
leaks the model's private reasoning (`</think>`) into the answer.
""")

md("""
## Step 6 — Start, stop, restart

All of these run on the GPU node, after `module load docker`.

| I want to | Command | Notes |
|---|---|---|
| Start it for the first time | `source ~/.ngc_key && bash ~/open-credit-evidence/scripts/cluster/serve_lightning.sh` | Needs a GPU session (Step 2). Downloads weights if not cached. |
| Start it again after a stop | `docker start nemotron-lightning` | Seconds, not minutes — image and weights are already there. Or run the script again; it notices the container exists. |
| Stop it | `docker stop nemotron-lightning` | Frees the GPU. The container is kept, so `docker start` brings it back. |
| Remove it completely | `docker rm -f nemotron-lightning` | Only if you need to change how it was started (different port, different GPU). The weights in `/data/team08/nim-cache` are not touched. |
| Watch what it is doing | `docker logs -f nemotron-lightning` | Ctrl-C stops watching, not the container. |
| See which GPU it holds | `nvidia-smi` | Memory used on one GPU, ~60 GB. |

Two things that surprise people:

- **The container outlives your SLURM session.** Typing `exit` on the GPU node
  releases your SLURM allocation but the container keeps running and keeps its GPU.
  That is what we want for a server. It also means the GPU stays busy until
  somebody runs `docker stop`, so stop it at the end of the day if nobody needs it.
- **`docker start` needs no NGC key.** The key is only for downloading. Once the
  weights are cached, restarting is offline.
""")

md("""
## Step 7 — Test it from your laptop, through our own code

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
That is the whole path: laptop → VPN → our own GPU → briefing → back, through the
same code that talks to the cloud, with the endpoint recorded on every response.

What we found when we ran real cases against it — speed, the arithmetic errors, and
why even our own server is not byte-for-byte reproducible — is logged in
`BUILD.md` under the 16 September change-log entry.
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
