#!/usr/bin/env bash
set -euo pipefail

export MERITRANK_LLM_ENDPOINT="${MERITRANK_LLM_ENDPOINT:-http://127.0.0.1:11434/v1/chat/completions}"
export MERITRANK_LLM_MODEL="${MERITRANK_LLM_MODEL:-qwen2.5:0.5b}"

if ! curl --silent --fail http://127.0.0.1:11434/api/tags >/dev/null; then
  ollama serve >/private/tmp/meritrank-ollama.log 2>&1 &
  sleep 2
fi

python3 -m talent_ranker.server

