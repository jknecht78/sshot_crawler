#!/bin/bash
# Starts the vLLM inference server (OpenAI-compatible API).
# Run this once; keep it running while main.py crawls.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$PROJECT_DIR/.env"

# Read a single key from .env safely
_env() { grep -m1 "^$1=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d '[:space:]'; }

# Determine which model config to load
MODEL_CONFIG="${MODEL_CONFIG:-$(_env MODEL_CONFIG)}"
MODEL_CONFIG="${MODEL_CONFIG:-qwen3-vl-8b}"

# Load model config — vars already set by the caller (e.g. benchmark.py) take priority
MODEL_CONFIG_FILE="$PROJECT_DIR/configs/$MODEL_CONFIG.env"
if [[ -f "$MODEL_CONFIG_FILE" ]]; then
    while IFS='=' read -r _k _v; do
        [[ "$_k" =~ ^[[:space:]]*# || -z "${_k// }" ]] && continue
        _k="${_k// /}"; _v="${_v// /}"
        [[ -v "$_k" ]] || export "$_k=$_v"
    done < "$MODEL_CONFIG_FILE"
fi

MODEL_ID="${MODEL_ID:-Qwen/Qwen3-VL-8B-Instruct}"
SERVER_HOST="${SERVER_HOST:-$(_env SERVER_HOST)}"
SERVER_HOST="${SERVER_HOST:-127.0.0.1}"
SERVER_PORT="${SERVER_PORT:-$(_env SERVER_PORT)}"
SERVER_PORT="${SERVER_PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-2048}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.90}"
VLLM_EXTRA_ARGS="${VLLM_EXTRA_ARGS:-}"

# Suppress warnings
export VLLM_LOGGING_LEVEL=ERROR
export TRANSFORMERS_VERBOSITY=error
export TORCH_CPP_LOG_LEVEL=ERROR
export HF_TOKEN="${HF_TOKEN:-$(_env HF_TOKEN)}"

source "$PROJECT_DIR/.venv/bin/activate"

cat << 'EOF'

                      (
                        )     (
                 ___...(-------)-....___
             .-""       )    (          ""-.
       .-'``'|-._             )         _.-|
      /  .--.|   `""---...........---""`   |
     /  /    |                             |
     |  |    |                             |
      \  \   |                             |
       `\ `\ |                             |
         `\ `|                             |
         _/ /\                             /
        (__/  \                           /
     _..---""` \                         /`""---.._
  .-'           \                       /          '-.
 :               `-.__             __.-'              :
 :                  ) ""---...---"" (                 :
  '._               `"--...___...--"`              _.'
    \""--..__                              __..--""/
     '._     """----.....______.....----"""     _.'
        `""--..,,_____            _____,,..--""`
                      `"""----"""`

    Grab a coffee while the server starts up.
EOF
echo "    vLLM Inference Server → CONFIG: $MODEL_CONFIG | MODEL: $MODEL_ID @ http://$SERVER_HOST:$SERVER_PORT"
echo ""
exec vllm serve "$MODEL_ID" \
    --host "$SERVER_HOST" \
    --port "$SERVER_PORT" \
    --max-model-len "$MAX_MODEL_LEN" \
    --gpu-memory-utilization "$GPU_MEM_UTIL" \
    --dtype float16 \
    --limit-mm-per-prompt '{"image":1}' \
    --enable-prefix-caching \
    --uvicorn-log-level error \
    $VLLM_EXTRA_ARGS
