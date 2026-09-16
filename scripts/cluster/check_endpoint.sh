#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Algoritmica GmbH
#
# One chat call against a NIM, from anywhere on the cluster (login node included).
#   bash scripts/cluster/check_endpoint.sh http://rtx-3se-05-36:8000/v1
set -euo pipefail
BASE=${1:?usage: check_endpoint.sh http://<node>:<port>/v1}
MODEL=${2:-nvidia/nemotron-3.5-lightning}
curl -s --noproxy '*' --max-time 120 -X POST "$BASE/chat/completions" \
  -H "Content-Type: application/json" \
  -d "{\"model\":\"$MODEL\",\"temperature\":0,\"seed\":7,\"max_tokens\":40,
       \"chat_template_kwargs\":{\"enable_thinking\":false},
       \"messages\":[{\"role\":\"system\",\"content\":\"Answer in one sentence.\"},
                     {\"role\":\"user\",\"content\":\"What is a debt-to-income ratio?\"}]}" \
  | python3 -c 'import json,sys; r=json.load(sys.stdin); print(r["model"], "|", r["choices"][0]["message"]["content"].strip())'
