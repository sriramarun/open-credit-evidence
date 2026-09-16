# The Codefest cluster

What we have, verified 16 Sep 2026, and how the framework uses it.

## Facts

| | |
|---|---|
| Login node | `10.130.232.14` over the `codefest.ovpn` VPN. No GPUs, no docker. SLURM commands need a login shell (`bash -l`). |
| Team node | `rtx-3se-05-36`: 8× RTX PRO 6000 Blackwell, 97.9 GB each. One node per team (`AssocGrpNodeLimit`). |
| Getting a GPU | `srun --gres=gpu:1 -n1 -p defq --time=HH:MM:SS --pty bash`. `$CUDA_VISIBLE_DEVICES` tells you which one you got. |
| Docker | On GPU nodes only: `module load docker`. Containers are node-level and **outside SLURM** — they survive your session and hold their GPU until stopped. `--gpus 1` takes GPU 0 regardless of your allocation; always use `--gpus "device=$CUDA_VISIBLE_DEVICES"`. |
| Proxy | Shell sets `HTTP(S)_PROXY=http://10.130.232.8:3128`. `NO_PROXY` already covers `localhost`, `127.0.0.1`, `10.0.0.0/8`. Containers need the proxy passed in to reach NGC; `curl --noproxy '*'` for anything on the node. |
| Egress | Works through the proxy: huggingface.co and nvcr.io both reachable. |
| Storage | `/home/<user>` 2 TB shared; `/data/team08` 2 TB team-shared, group-writable — model weights and checkpoints go here; node-local `/raid` 47 TB scratch. |
| Already on the node | `nvcr.io/nim/nvidia/nemotron-3.5-lightning-30b-a3b:2.0.9-variant` (NIM), `nvcr.io/nvidia/nemo:26.08.00` (NeMo framework, for the Nano LoRA), CUDA 12.9 toolkit module, Python 3.12. |
| Accounts | Sriram is `team08_user3`. Key-based ssh: `ssh codefest`. Keep the NGC key in `~/.ngc_key` (mode 600) and `source` it — not on the command line, which lands in `.bash_history`. |

## What runs where

| Role | Where | Why |
|---|---|---|
| Assistant (Lightning) | NIM on the team node | Fixed seed on a local vLLM is reproducible; the free endpoint was not, and took 8–150 s per call. Runner at volume needs both. |
| Judge (Ultra, teacher) | NVIDIA Build | 550B; serving it would take the whole node. A few hundred labels at 40 rpm is fine. |
| Judge (Nano, student) | NIM on the team node, once trained | The on-prem story: loan files never leave the box. |
| Embed | NVIDIA Build for now | Tiny call volume. Move on-node if latency matters. |

Switching a role is two lines in `.env`; see `.env.example`. Every `ChatResponse`
records its `endpoint`, so a transcript can always say cloud or on-prem.

## Serving Lightning

```
ssh codefest
srun --gres=gpu:1 -n1 -p defq --time=08:00:00 --pty bash
source ~/.ngc_key
bash ~/open-credit-evidence/scripts/cluster/serve_lightning.sh
```

The script waits for the health check and prints the `.env` lines. From the login
node or another GPU session, `scripts/cluster/check_endpoint.sh http://rtx-3se-05-36:8000/v1`
makes one chat call. To stop: `docker stop nemotron-lightning` on the node.

## GPU budget (8 GPUs, three people)

| GPU | Use |
|---|---|
| one | Lightning NIM, long-lived |
| one | Nano judge NIM, once trained |
| one–two | LoRA training (`nemo:26.08.00`) |
| rest | interactive work |

## Gotchas found so far

- `squeue` only shows our own account; a node that looks idle to us may be full.
- The NIM's `/v1/completions` with a raw prompt leaks `</think>` into the text. We
  use `/v1/chat/completions` with `enable_thinking` set explicitly; confirm on the
  first call.
- Running `docker` on the login node fails with a socket permission error — that
  is expected, it only exists on GPU nodes.
