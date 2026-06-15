# AIS-Bench Performance Client

> 中文文档见 [README.zh.md](./README.zh.md)

An [AIS-Bench](https://github.com/AISBench/benchmark) benchmark **client** image
for measuring LLM serving performance (TTFT, TPOT, throughput) of an
OpenAI-compatible endpoint — e.g. a vLLM-Ascend service running on NPU.

> **This is a client.** Perf mode sends HTTP requests to a remote endpoint and
> only needs the served model's **tokenizer** locally (to generate exact-length
> inputs and count tokens). The NPU lives on the serving side, so this image is
> CPU-only.

## Build

```bash
# from the ascend-docker-factory/ repo root (build context = repo root)
docker build -f projects/ais-bench/Dockerfile -t ais-bench:local --platform linux/arm64 .
```

Build args: `GIT_TAG` (pin an AIS-Bench release, default `latest`),
`PIP_INDEX_URL` (pip mirror), `TTYD_VERSION`.

**ttyd note:** the web terminal binary is downloaded from GitHub at build time.
If your build network can't reach GitHub over TLS, drop a prebuilt
`ttyd.aarch64` into `projects/ais-bench/vendor/` (gitignored) and the build will
use it instead of downloading.

## Tokenizer

`tokenid` synthetic inputs need the served model's tokenizer. Mount its
directory (containing `tokenizer.json` + `tokenizer_config.json`) at `/tok`:

```bash
-v /path/to/model/tokenizer_dir:/tok:ro
```

## Auth & self-signed TLS

- **API key:** pass `-e AIS_API_KEY=<token>`. It is sent as
  `Authorization: Bearer <token>`. Never bake it into a config file.
- **Self-signed HTTPS:** pass `-e AIS_INSECURE_SSL=1` to disable TLS
  verification (aiohttp ignores `PYTHONHTTPSVERIFY`; the image's
  `sitecustomize.py` patches the SSL context instead).

## Running a benchmark

```bash
docker run --rm --platform linux/arm64 \
  -e AIS_API_KEY="$AIS_API_KEY" -e AIS_INSECURE_SSL=1 \
  -v /path/to/tokenizer:/tok:ro \
  ais-bench:local \
  run_bench.sh --url "https://HOST/.../v1" -c 8 -i 8192 -o 1024 -n 80
```

### `run_bench.sh` flags

| Flag | Meaning | Maps to | Default |
|------|---------|---------|---------|
| `-c, --concurrency` | concurrent in-flight requests | `batch_size` | 8 |
| `-i, --input-tokens` | synthetic input length | `TokenIdConfig.RequestSize` | 8192 |
| `-o, --output-tokens` | max output tokens | `max_out_len` | 1024 |
| `-n, --num-requests` | total requests | `RequestCount` | 50 |
| `--rate` | open-loop arrival rate (req/s); 0 = unbounded | `request_rate` | 0 |
| `--model` | served model name | `model`/`abbr` | deepseek_v4 |
| `--url` | endpoint base URL ending in `/v1` (no trailing slash) | `url` | (required) |
| `--num-warmups` | warmup requests (excluded from metrics) | CLI | 8 |
| `--no-ignore-eos` | let the model stop early | `ignore_eos=False` | off |

## Preset matrix

Concurrency **{1, 8, 16, 32, 64}** × output **1024 tokens**, with `-n` scaled to
concurrency (`n ≈ max(50, c×5)`) so each run reaches steady state. Set
`URL=https://HOST/.../v1` first.

**8K input:**

```bash
run_bench.sh --url "$URL" -c 1  -i 8192 -o 1024 -n 50
run_bench.sh --url "$URL" -c 8  -i 8192 -o 1024 -n 80
run_bench.sh --url "$URL" -c 16 -i 8192 -o 1024 -n 120
run_bench.sh --url "$URL" -c 32 -i 8192 -o 1024 -n 200
run_bench.sh --url "$URL" -c 64 -i 8192 -o 1024 -n 320
```

**32K input:**

```bash
run_bench.sh --url "$URL" -c 1  -i 32768 -o 1024 -n 50
run_bench.sh --url "$URL" -c 8  -i 32768 -o 1024 -n 80
run_bench.sh --url "$URL" -c 16 -i 32768 -o 1024 -n 120
run_bench.sh --url "$URL" -c 32 -i 32768 -o 1024 -n 200
run_bench.sh --url "$URL" -c 64 -i 32768 -o 1024 -n 320
```

> The endpoint's `max_model_len` must be ≥ input + output. Check
> `GET <url>/models`.

## Interpreting the metrics

| Metric | Meaning |
|--------|---------|
| **TTFT** | time to first token |
| **TPOT** | per-output-token latency (steady-state decode) |
| **ITL** | inter-token latency |
| **E2EL** | end-to-end request latency |
| **Output/Total Token Throughput** | aggregate tokens/s across all concurrent streams |
| **Max Concurrency** | should equal `-c` (driven by `batch_size`) |

Load model: `batch_size` (= `-c`) caps in-flight requests (closed-loop). Set
`--rate` > 0 for open-loop arrival pacing; concurrency then floats =
`rate × latency`, still capped by `-c`. Warmup requests are **excluded** from
reported metrics.

## Web terminal

The image's default `CMD` runs `ttyd` on port **7681** — run with `-p 7681:7681`
and open `http://localhost:7681` for an in-browser shell.

## Troubleshooting

- **`invalid syntax ... os=<module ...>`** — a config referenced a runtime object
  (e.g. `os.environ`). Configs are serialized and re-parsed; use only literals.
  `run_bench.sh` handles this by substituting values into a temp config.
- **`Couldn't instantiate the backend tokenizer ... sentencepiece`** — the
  tokenizer needs SentencePiece; this image ships it. Ensure `/tok` has a valid
  tokenizer.
- **TLS / cert errors** — set `AIS_INSECURE_SSL=1`.
- **`Not Found` on every request** — the endpoint URL/service is wrong or the
  service was deprovisioned; verify with `curl <url>/models`.
- **Context-length rejection** — input+output exceeds the endpoint's
  `max_model_len`; lower `-i`/`-o`.

## Local offline test (no endpoint)

`mock_llm.py` is a fake OpenAI-compatible server for smoke-testing the pipeline
without a real endpoint:

```bash
docker run --rm --platform linux/arm64 \
  -v /path/to/tokenizer:/tok:ro \
  -v "$PWD/projects/ais-bench:/proj:ro" \
  ais-bench:local bash -c '
    python3 /proj/mock_llm.py >/tmp/mock.log 2>&1 &
    sleep 2
    run_bench.sh --url "http://localhost:8000/v1" --model mock-model -c 4 -i 512 -o 64 -n 12'
```

`test_mock_config.py` and `deepseek_v4_perf.py` are hand-written single-config
examples for reference.
