#!/usr/bin/env bash
# Fail if anything a config needs would have to be downloaded at RUN time.
#
# The NPU box has no route out: it runs with HF_HUB_OFFLINE=1 against a
# read-only weights mount. Every asset must therefore be staged BEFORE the
# image is built. A dataset or model that resolves to a hub id is a training run
# that dies on that box — and it dies late, after the queue wait and the
# container start.
#
# Run from the repo root (or anywhere; paths resolve relative to this script):
#   ./projects/llama-factory/preflight-offline.sh
#
# Exit 0 means every referenced asset is local.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAIL=0

note() { printf '  %-52s %s\n' "$1" "$2"; }
fail() { note "$1" "FAIL: $2"; FAIL=1; }

echo "=== configs: model paths must be local, not hub ids ==="
for cfg in "$HERE"/configs/npu-*.yaml; do
    [ -e "$cfg" ] || continue
    model="$(grep -E '^model_name_or_path:' "$cfg" | head -1 | sed 's/^model_name_or_path:[[:space:]]*//')"
    if [[ "$model" == /* ]]; then
        note "$(basename "$cfg")" "local path OK ($model)"
    else
        fail "$(basename "$cfg")" "hub id '$model' — would download at run time"
    fi
done

echo
echo "=== configs: dataset_dir must be pinned absolutely ==="
# llamafactory-cli resolves a relative dataset_dir against the CWD, and the
# image WORKDIR (/home/ma-user) is not where the datasets are baked.
for cfg in "$HERE"/configs/npu-*.yaml; do
    [ -e "$cfg" ] || continue
    dir="$(grep -E '^dataset_dir:' "$cfg" | head -1 | sed 's/^dataset_dir:[[:space:]]*//')"
    if [[ "$dir" == /* ]]; then
        note "$(basename "$cfg")" "pinned OK ($dir)"
    else
        fail "$(basename "$cfg")" "dataset_dir '${dir:-<unset>}' is not absolute"
    fi
done

echo
echo "=== configs: every named dataset must be registered and present ==="
for cfg in "$HERE"/configs/npu-*.yaml; do
    [ -e "$cfg" ] || continue
    line="$(grep -E '^dataset:' "$cfg" | head -1 | sed 's/^dataset:[[:space:]]*//')"
    IFS=',' read -ra names <<< "$line"
    for n in "${names[@]}"; do
        n="$(echo "$n" | xargs)"
        [ -z "$n" ] && continue
        if ! python3 - "$HERE" "$n" "$(basename "$cfg")" <<'PY'
import json, os, sys
root, name, cfg = sys.argv[1], sys.argv[2], sys.argv[3]
reg = json.load(open(os.path.join(root, 'data', 'dataset_info.json'), encoding='utf-8'))
label = f"{cfg}:{name}"
if name not in reg:
    print(f"  {label:<52} FAIL: not in dataset_info.json"); sys.exit(1)
e = reg[name]
if {'hf_hub_url', 'ms_hub_url', 'script_url'} & e.keys():
    print(f"  {label:<52} FAIL: resolves to a remote hub url"); sys.exit(1)
f = os.path.join(root, 'data', e.get('file_name', ''))
if not os.path.exists(f):
    print(f"  {label:<52} FAIL: file missing ({e.get('file_name')})"); sys.exit(1)
print(f"  {label:<52} staged OK ({len(json.load(open(f, encoding='utf-8')))} records)")
PY
        then FAIL=1; fi
    done
done

echo
echo "=== registrations must not outnumber shipped files ==="
# LLaMA-Factory validates every entry in dataset_info.json, so a registration
# whose file is absent breaks the run even if no config names it.
python3 - "$HERE" <<'PY' || FAIL=1
import json, os, sys
root = sys.argv[1]
reg = json.load(open(os.path.join(root, 'data', 'dataset_info.json'), encoding='utf-8'))
bad = [k for k, v in reg.items()
       if 'file_name' in v and not os.path.exists(os.path.join(root, 'data', v['file_name']))]
if bad:
    print(f"  {'orphan registrations':<52} FAIL: {', '.join(bad)}"); sys.exit(1)
print(f"  {'all ' + str(len(reg)) + ' registrations have files':<52} OK")
PY

echo
echo "=== identity placeholders substituted? ==="
if [ -f "$HERE/data/identity.json" ]; then
    left="$(grep -c '{{' "$HERE/data/identity.json" || true)"
    if [ "$left" = "0" ]; then
        note "identity.json" "no placeholders OK"
    else
        fail "identity.json" "$left placeholders remain"
    fi
fi

echo
if [ "$FAIL" -eq 0 ]; then
    echo "PREFLIGHT PASS — every referenced asset is staged locally."
else
    echo "PREFLIGHT FAIL — fix the above before building; the NPU box cannot download." >&2
fi
exit "$FAIL"
