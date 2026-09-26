#!/usr/bin/env bash
set -euo pipefail

MODEL=""
URL=""
DATASET=""
OUTPUT_TOKENS=2048
CONCURRENCY=1
TEMPLATE="${AIS_ACC_TEMPLATE:-/opt/ais-bench/accuracy_template.py}"

# dataset key -> "dotted_module|datasets_var|on_disk_dir"
# (verified against AISBench source; configs name their list <key>_datasets)
declare -A ACC=(
    [gsm8k]="gsm8k.gsm8k_gen_0_shot_cot_chat_prompt|gsm8k_datasets|gsm8k"
    [ceval]="ceval.ceval_gen_0_shot_cot_chat_prompt|ceval_datasets|ceval/formal_ceval"
    [mmlu]="mmlu.mmlu_gen_0_shot_cot_chat_prompt|mmlu_datasets|mmlu"
    [gpqa]="gpqa.gpqa_gen_0_shot_str|gpqa_datasets|gpqa"
    [math500]="math.math500_gen_0_shot_cot_chat_prompt|math_datasets|math"
    [aime]="aime2024.aime2024_gen_0_shot_chat_prompt|aime2024_datasets|aime"
)

usage() {
    cat <<EOF
Usage: run_eval.sh --url <endpoint/v1> --model NAME --dataset KEY [options]

  --url URL          Endpoint base URL ending in /v1 (no trailing slash). Required
  --model NAME       Served model name. Required
  --dataset KEY      One of: ${!ACC[*]}. Required
  -o, --output-tokens N  max_out_len. Default 2048
  -c, --concurrency N    batch_size. Default 1
  -h, --help

Environment:
  AIS_API_KEY        Bearer token (required if auth enabled)
  AIS_INSECURE_SSL=1 Disable TLS verification (self-signed certs)
  Tokenizer must be mounted at /tok.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --url) URL="$2"; shift 2 ;;
        --model) MODEL="$2"; shift 2 ;;
        --dataset) DATASET="$2"; shift 2 ;;
        -o|--output-tokens) OUTPUT_TOKENS="$2"; shift 2 ;;
        -c|--concurrency) CONCURRENCY="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unknown arg: $1" >&2; usage; exit 1 ;;
    esac
done

[[ -z "$URL" ]] && { echo "ERROR: --url required" >&2; usage; exit 1; }
[[ -z "$MODEL" ]] && { echo "ERROR: --model required" >&2; usage; exit 1; }
[[ -z "$DATASET" ]] && { echo "ERROR: --dataset required" >&2; usage; exit 1; }
SPEC="${ACC[$DATASET]:-}"
[[ -z "$SPEC" ]] && { echo "ERROR: unknown dataset '$DATASET'. Valid: ${!ACC[*]}" >&2; exit 1; }
IFS='|' read -r MODULE DATASETS_VAR DSDIR <<< "$SPEC"

if [[ ! -f /tok/tokenizer.json && ! -f /tok/tokenizer.model ]]; then
    echo "ERROR: no tokenizer at /tok (mount tokenizer dir to /tok)" >&2; exit 1
fi
if [[ ! -d "/benchmark/ais_bench/datasets/$DSDIR" ]]; then
    echo "ERROR: dataset '$DSDIR' not in image. Run fetch_datasets.sh and rebuild." >&2; exit 1
fi

API_KEY="${AIS_API_KEY:-}"
CFG="$(mktemp /tmp/ais_acc_XXXX.py)"
trap 'rm -f "$CFG"' EXIT
sed \
    -e "s|__DATASET_MODULE__|${MODULE}|g" \
    -e "s|__DATASETS_VAR__|${DATASETS_VAR}|g" \
    -e "s|__OUTPUT_TOKENS__|${OUTPUT_TOKENS}|g" \
    -e "s|__CONCURRENCY__|${CONCURRENCY}|g" \
    -e "s|__MODEL__|${MODEL}|g" \
    -e "s|__URL__|${URL}|g" \
    -e "s|__API_KEY__|${API_KEY}|g" \
    "$TEMPLATE" > "$CFG"

echo ">>> accuracy: dataset=${DATASET} (${MODULE}) model=${MODEL} c=${CONCURRENCY} out=${OUTPUT_TOKENS}"
cd /benchmark
exec ais_bench "$CFG" --mode all --dump-eval-details --merge-ds
