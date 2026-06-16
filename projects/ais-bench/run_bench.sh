#!/usr/bin/env bash
set -euo pipefail

# Defaults
CONCURRENCY=8
INPUT_TOKENS=8192
OUTPUT_TOKENS=1024
NUM_REQUESTS=50
REQUEST_RATE=0
MODEL="deepseek_v4"
URL=""
FULL_URL=""
NUM_WARMUPS=8
IGNORE_EOS="True"
TEMPLATE="${AIS_PERF_TEMPLATE:-/opt/ais-bench/perf_template.py}"

usage() {
    cat <<'EOF'
Usage: run_bench.sh --url <endpoint/v1> [options]

  -c, --concurrency N    Concurrent in-flight requests (batch_size). Default 8
  -i, --input-tokens N   Synthetic input length in tokens. Default 8192
  -o, --output-tokens N  Max output tokens (max_out_len). Default 1024
  -n, --num-requests N   Total benchmark requests. Default 50
      --rate F           Open-loop arrival rate (req/s); 0 = unbounded. Default 0
      --model NAME       Served model name. Default deepseek_v4
      --url URL          Endpoint base URL ending in /v1 (no trailing slash). Required
      --full-url URL     Exact chat/completions URL, posted verbatim. Use for
                         non-/v1 paths (e.g. .../api/v2/chat/completions). When
                         set, --url may be any base (used only as a placeholder).
      --num-warmups N    Warmup requests (excluded from metrics). Default 8
      --no-ignore-eos    Let the model stop naturally (default forces full output)
  -h, --help             Show this help

Environment:
  AIS_API_KEY            Bearer token for the endpoint (required if auth enabled)
  AIS_INSECURE_SSL=1     Disable TLS verification (self-signed certs)
  Tokenizer must be mounted at /tok (tokenizer.json + tokenizer_config.json).
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -c|--concurrency) CONCURRENCY="$2"; shift 2 ;;
        -i|--input-tokens) INPUT_TOKENS="$2"; shift 2 ;;
        -o|--output-tokens) OUTPUT_TOKENS="$2"; shift 2 ;;
        -n|--num-requests) NUM_REQUESTS="$2"; shift 2 ;;
        --rate) REQUEST_RATE="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --url) URL="$2"; shift 2 ;;
        --full-url) FULL_URL="$2"; shift 2 ;;
        --num-warmups) NUM_WARMUPS="$2"; shift 2 ;;
        --no-ignore-eos) IGNORE_EOS="False"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
    esac
done

# When --full-url is given, it is the verbatim request URL; --url only seeds the
# config's base_url placeholder, so default it to the full URL if unset.
if [[ -n "$FULL_URL" ]]; then
    export AIS_FULL_URL="$FULL_URL"
    URL="${URL:-$FULL_URL}"
fi
if [[ -z "$URL" ]]; then echo "ERROR: --url or --full-url is required" >&2; usage; exit 1; fi
if [[ ! -f /tok/tokenizer.json && ! -f /tok/tokenizer.model ]]; then
    echo "ERROR: no tokenizer at /tok (mount tokenizer dir to /tok)" >&2; exit 1
fi

API_KEY="${AIS_API_KEY:-}"
CFG="$(mktemp /tmp/ais_perf_XXXX.py)"
trap 'rm -f "$CFG"' EXIT

sed \
    -e "s|__NUM_REQUESTS__|${NUM_REQUESTS}|g" \
    -e "s|__INPUT_TOKENS__|${INPUT_TOKENS}|g" \
    -e "s|__OUTPUT_TOKENS__|${OUTPUT_TOKENS}|g" \
    -e "s|__CONCURRENCY__|${CONCURRENCY}|g" \
    -e "s|__REQUEST_RATE__|${REQUEST_RATE}|g" \
    -e "s|__IGNORE_EOS__|${IGNORE_EOS}|g" \
    -e "s|__MODEL__|${MODEL}|g" \
    -e "s|__URL__|${URL}|g" \
    -e "s|__API_KEY__|${API_KEY}|g" \
    "$TEMPLATE" > "$CFG"

echo ">>> bench: c=${CONCURRENCY} in=${INPUT_TOKENS} out=${OUTPUT_TOKENS} n=${NUM_REQUESTS} rate=${REQUEST_RATE} warmups=${NUM_WARMUPS} model=${MODEL}${FULL_URL:+ endpoint=${FULL_URL}}"
cd /benchmark
exec ais_bench "$CFG" -m perf --max-num-workers 1 --num-warmups "${NUM_WARMUPS}"
