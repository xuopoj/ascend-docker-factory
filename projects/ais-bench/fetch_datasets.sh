#!/usr/bin/env bash
# Run-once host helper: download + unpack the 6 AISBench text datasets into
# projects/ais-bench/datasets/ so the Dockerfile can COPY them into the image.
# Layout matches what AISBench dataset configs expect under /benchmark/ais_bench/datasets/.
set -euo pipefail

DEST="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/datasets"
mkdir -p "$DEST"

OSS="http://opencompass.oss-cn-shanghai.aliyuncs.com/datasets/data"
CEVAL_URL="https://www.modelscope.cn/datasets/opencompass/ceval-exam/resolve/master/ceval-exam.zip"

fetch() {  # fetch <url> <out.zip>
    local url="$1" out="$2"
    echo ">>> downloading $url"
    curl -fSL --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 20 -o "$out" "$url"
    test -s "$out"
}

# unpack <zip> <target_dir>: unzip archive into target_dir (created if needed)
unpack() {
    local zip="$1" target="$2"
    mkdir -p "$target"
    unzip -q -o "$zip" -d "$target"
    rm -f "$zip"
}

have() { [ -d "$DEST/$1" ] && [ -n "$(ls -A "$DEST/$1" 2>/dev/null)" ]; }

# self-wrapping zips: unzip straight into DEST -> DEST/<name>/
for name in gsm8k mmlu gpqa math; do
    if have "$name"; then echo "== $name present, skip"; continue; fi
    fetch "$OSS/$name.zip" "$DEST/$name.zip"
    unpack "$DEST/$name.zip" "$DEST"
done

# aime: bare aime.jsonl -> DEST/aime/aime.jsonl
if have aime; then echo "== aime present, skip"; else
    fetch "$OSS/aime.zip" "$DEST/aime.zip"
    unpack "$DEST/aime.zip" "$DEST/aime"
fi

# ceval: dev/ val/ test/ -> DEST/ceval/formal_ceval/{dev,val,test}/
if [ -d "$DEST/ceval/formal_ceval" ] && [ -n "$(ls -A "$DEST/ceval/formal_ceval" 2>/dev/null)" ]; then
    echo "== ceval present, skip"
else
    fetch "$CEVAL_URL" "$DEST/ceval.zip"
    unpack "$DEST/ceval.zip" "$DEST/ceval/formal_ceval"
fi

echo ">>> done. datasets under $DEST:"
for d in gsm8k mmlu gpqa math aime ceval/formal_ceval; do
    n=$(find "$DEST/$d" -type f 2>/dev/null | wc -l | tr -d ' ')
    echo "   $d: $n files"
done
