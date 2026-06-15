# AIS-Bench 性能测试客户端

> English docs: [README.md](./README.md)

一个 [AIS-Bench](https://github.com/AISBench/benchmark) 基准测试**客户端**镜像，
用于测量 OpenAI 兼容推理服务的性能（TTFT、TPOT、吞吐量）——例如运行在 NPU 上的
vLLM-Ascend 服务。

> **这是一个客户端。** 性能（perf）模式向远端推理服务发送 HTTP 请求，本地只需要被测
> 模型的**分词器**（用于生成精确长度的输入并统计 token 数）。NPU 在服务端，因此本镜像
> 是纯 CPU 的。

## 构建镜像

```bash
# 在 ascend-docker-factory/ 仓库根目录执行（构建上下文 = 仓库根目录）
docker build -f projects/ais-bench/Dockerfile -t ais-bench:local --platform linux/arm64 .
```

构建参数：`GIT_TAG`（固定 AIS-Bench 版本，默认 `latest`）、`PIP_INDEX_URL`
（pip 镜像源）、`TTYD_VERSION`。

**ttyd 说明：** Web 终端二进制在构建时从 GitHub 下载。如果构建网络无法通过 TLS 访问
GitHub，可将预先下载好的 `ttyd.aarch64` 放入 `projects/ais-bench/vendor/`
（已被 gitignore），构建时会优先使用它而不再下载。

## 分词器

`tokenid` 合成输入需要被测模型的分词器。将其目录（包含 `tokenizer.json` +
`tokenizer_config.json`）挂载到 `/tok`：

```bash
-v /path/to/model/tokenizer_dir:/tok:ro
```

## 认证与自签名 TLS

- **API key：** 通过 `-e AIS_API_KEY=<token>` 传入。它会以
  `Authorization: Bearer <token>` 发送。**切勿**写入配置文件。
- **自签名 HTTPS：** 通过 `-e AIS_INSECURE_SSL=1` 关闭 TLS 校验（aiohttp 会忽略
  `PYTHONHTTPSVERIFY`，镜像内的 `sitecustomize.py` 会改为修补 SSL 上下文）。

## 运行基准测试

```bash
docker run --rm --platform linux/arm64 \
  -e AIS_API_KEY="$AIS_API_KEY" -e AIS_INSECURE_SSL=1 \
  -v /path/to/tokenizer:/tok:ro \
  ais-bench:local \
  run_bench.sh --url "https://HOST/.../v1" -c 8 -i 8192 -o 1024 -n 80
```

### `run_bench.sh` 参数

| 参数 | 含义 | 对应配置 | 默认值 |
|------|------|----------|--------|
| `-c, --concurrency` | 并发的在途请求数 | `batch_size` | 8 |
| `-i, --input-tokens` | 合成输入长度 | `TokenIdConfig.RequestSize` | 8192 |
| `-o, --output-tokens` | 最大输出 token 数 | `max_out_len` | 1024 |
| `-n, --num-requests` | 总请求数 | `RequestCount` | 50 |
| `--rate` | 开环到达速率（req/s）；0 = 不限速 | `request_rate` | 0 |
| `--model` | 被测模型名 | `model`/`abbr` | deepseek_v4 |
| `--url` | 以 `/v1` 结尾的服务 URL（无尾部斜杠） | `url` | （必填） |
| `--num-warmups` | 预热请求数（不计入指标） | CLI | 8 |
| `--no-ignore-eos` | 允许模型提前停止 | `ignore_eos=False` | 关闭 |

## 预设组合

并发 **{1, 8, 16, 32, 64}** × 输出 **1024 tokens**，`-n` 随并发数缩放
（`n ≈ max(50, c×5)`）以使每次运行达到稳定状态。先设置 `URL=https://HOST/.../v1`。

**8K 输入：**

```bash
run_bench.sh --url "$URL" -c 1  -i 8192 -o 1024 -n 50
run_bench.sh --url "$URL" -c 8  -i 8192 -o 1024 -n 80
run_bench.sh --url "$URL" -c 16 -i 8192 -o 1024 -n 120
run_bench.sh --url "$URL" -c 32 -i 8192 -o 1024 -n 200
run_bench.sh --url "$URL" -c 64 -i 8192 -o 1024 -n 320
```

**32K 输入：**

```bash
run_bench.sh --url "$URL" -c 1  -i 32768 -o 1024 -n 50
run_bench.sh --url "$URL" -c 8  -i 32768 -o 1024 -n 80
run_bench.sh --url "$URL" -c 16 -i 32768 -o 1024 -n 120
run_bench.sh --url "$URL" -c 32 -i 32768 -o 1024 -n 200
run_bench.sh --url "$URL" -c 64 -i 32768 -o 1024 -n 320
```

> 服务的 `max_model_len` 必须 ≥ 输入 + 输出。可通过 `GET <url>/models` 查看。

## 指标解读

| 指标 | 含义 |
|------|------|
| **TTFT** | 首 token 时延 |
| **TPOT** | 每输出 token 时延（稳态解码） |
| **ITL** | token 间时延 |
| **E2EL** | 端到端请求时延 |
| **Output/Total Token Throughput** | 所有并发流的聚合 token/s |
| **Max Concurrency** | 应等于 `-c`（由 `batch_size` 驱动） |

负载模型：`batch_size`（即 `-c`）限制在途请求数（闭环）。设置 `--rate` > 0 可启用
开环到达节流；此时并发浮动 = `速率 × 时延`，仍受 `-c` 上限约束。预热请求**不计入**
上报的指标。

## Web 终端

镜像默认 `CMD` 在 **7681** 端口运行 `ttyd`——用 `-p 7681:7681` 运行后，打开
`http://localhost:7681` 即可获得浏览器内的终端。

## 故障排查

- **`invalid syntax ... os=<module ...>`** —— 配置引用了运行时对象（如
  `os.environ`）。配置会被序列化后重新解析，只能使用字面量。`run_bench.sh` 通过把值
  替换进临时配置来规避此问题。
- **`Couldn't instantiate the backend tokenizer ... sentencepiece`** —— 分词器
  需要 SentencePiece，本镜像已内置。请确认 `/tok` 下有有效的分词器。
- **TLS / 证书错误** —— 设置 `AIS_INSECURE_SSL=1`。
- **每个请求都 `Not Found`** —— 服务 URL 错误或服务已被下线；用
  `curl <url>/models` 验证。
- **上下文长度被拒绝** —— 输入+输出超过服务的 `max_model_len`；调小 `-i`/`-o`。

## 本地离线测试（无需服务端）

`mock_llm.py` 是一个 OpenAI 兼容的假服务，用于在没有真实服务端时冒烟测试整条流水线：

```bash
docker run --rm --platform linux/arm64 \
  -v /path/to/tokenizer:/tok:ro \
  -v "$PWD/projects/ais-bench:/proj:ro" \
  ais-bench:local bash -c '
    python3 /proj/mock_llm.py >/tmp/mock.log 2>&1 &
    sleep 2
    run_bench.sh --url "http://localhost:8000/v1" --model mock-model -c 4 -i 512 -o 64 -n 12'
```

`test_mock_config.py` 与 `deepseek_v4_perf.py` 是供参考的手写单文件配置示例。
