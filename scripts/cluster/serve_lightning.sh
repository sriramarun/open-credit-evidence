#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
#
# Serve Nemotron 3.5 Lightning as a NIM on the team's Codefest node.
#
# Run this INSIDE an srun session on the GPU node, never on the login node:
#
#   srun --gres=gpu:1 -n1 -p defq --time=08:00:00 --pty bash
#   bash ~/open-credit-evidence/scripts/cluster/serve_lightning.sh
#
# What it does, and why each line is there:
#   - uses the GPU SLURM gave you ($CUDA_VISIBLE_DEVICES), not "--gpus 1", which
#     silently takes GPU 0 whether or not it is yours;
#   - keeps the weight cache on /data/team08 so the ~60 GB download happens once
#     for the whole team, not once per home directory;
#   - passes the cluster's HTTP proxy into the container so it can reach NGC,
#     and talks to the container on localhost with the proxy bypassed;
#   - waits for the health check and prints the two lines to put in .env.
#
# The container keeps running after you leave the srun session (docker is
# node-level, outside SLURM), so the GPU stays busy until you `docker stop` it.
set -euo pipefail

NAME=${NAME:-nemotron-lightning}
IMAGE=${IMAGE:-nvcr.io/nim/nvidia/nemotron-3.5-lightning-30b-a3b:2.0.9-variant}
PORT=${NIM_PORT:-8000}
CACHE=${LOCAL_NIM_CACHE:-/data/team08/nim-cache}
PROXY=${HTTPS_PROXY:-http://10.130.232.8:3128}

if [[ "$(hostname)" == *login* ]]; then
  echo "This is the login node. Start an srun session first (see header)." >&2
  exit 1
fi
if [[ -z "${NGC_API_KEY:-}" ]]; then
  echo "NGC_API_KEY is not set. export it (from ~/.ngc_key, not your history)." >&2
  exit 1
fi
: "${CUDA_VISIBLE_DEVICES:?not inside an srun allocation — no GPU assigned}"

module load docker 2>/dev/null || true
mkdir -p "$CACHE"
chmod g+rwx "$CACHE" 2>/dev/null || true

if docker ps --format '{{.Names}}' | grep -qx "$NAME"; then
  echo "$NAME is already running:"
  docker ps --filter "name=$NAME" --format '  {{.Image}}  {{.Status}}'
else
  # Another server (a teammate's container, say) may already hold the port. The NIM
  # would start, fail on the port, and exit -- and a health poll would then be
  # answered by the other server and look like success. Refuse instead.
  if ss -tln 2>/dev/null | grep -q ":${PORT} "; then
    echo "port $PORT is already in use on $(hostname):" >&2
    docker ps --format '  {{.Names}}  {{.Image}}  {{.Status}}' 2>/dev/null >&2 || true
    echo "either use that server, or start ours on another port: NIM_PORT=8001 $0" >&2
    exit 1
  fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  echo "starting $NAME on GPU(s) $CUDA_VISIBLE_DEVICES, cache $CACHE, port $PORT"
  docker run -d \
    --name "$NAME" \
    --gpus "\"device=${CUDA_VISIBLE_DEVICES}\"" \
    --shm-size=16GB \
    --network host \
    -e NGC_API_KEY \
    -e NIM_SERVED_MODEL_NAME=nvidia/nemotron-3.5-lightning \
    -e NIM_SERVER_PORT="$PORT" -e NIM_HEALTH_PORT="$PORT" \
    -e HTTP_PROXY="$PROXY" -e HTTPS_PROXY="$PROXY" \
    -e http_proxy="$PROXY" -e https_proxy="$PROXY" \
    -e NO_PROXY="${NO_PROXY:-localhost,127.0.0.1}" -e no_proxy="${no_proxy:-localhost,127.0.0.1}" \
    -u "$(id -u)" \
    -v "$CACHE:/opt/nim/.cache" \
    "$IMAGE" >/dev/null
fi

echo -n "waiting for health"
for _ in $(seq 1 180); do
  if [[ "$(docker inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" != "true" ]]; then
    echo " $NAME has stopped. Last lines of its log:" >&2
    docker logs --tail 15 "$NAME" >&2
    exit 1
  fi
  if curl -s --noproxy '*' --max-time 3 "http://127.0.0.1:${PORT}/v1/health/ready" | grep -q '"ready"'; then
    echo " ready"
    break
  fi
  echo -n "."
  sleep 10
done

echo
echo "models served:"
curl -s --noproxy '*' "http://127.0.0.1:${PORT}/v1/models" | python3 -c 'import json,sys; [print("  " + m["id"]) for m in json.load(sys.stdin)["data"]]' \
  || { echo "  (not ready yet — docker logs -f $NAME)"; exit 1; }

echo
echo "put these two lines in .env on the machine running the evaluation:"
echo "  EVIDENCE_ASSISTANT_BASE_URL=http://$(hostname):${PORT}/v1"
echo "  EVIDENCE_ASSISTANT_MODEL=nvidia/nemotron-3.5-lightning"
