# LLM Benchmark

## How to benchmark a LLM

### Metrics

#### TTFT (Time to First Token)

How long from sending the request until the server returns the very first word?

* Why it matters: This is the "perceived latency" for the user. If this is high, the app feels unresponsive. It measures the Prefill speed.

#### TPOT (Time Per Output Token)

Once generation starts, how fast do tokens appear?

* Why it matters: This is the "reading speed." If this usage is lower than human reading speed (approx ~5-10 tokens/sec), the UI feels complete but laggy.

#### Total Latency

The total time for the request.

#### Throughput

* RPS (Requests Per Second): How many concurrent users can hit the endpoint?
* TPS (Tokens Per Second): The raw generation power of your GPU(s).

### The Benchmarking Strategy

We typically approach this in two ways:
Static Load Test: We fire X requests at exactly the same time (Concurrency check) to see when the Queue fills up and TTFT spikes.
Ramp-up Test: We start with 1 user, then 2, then 4, until the system crashes or latency becomes unacceptable.

## Datasets

### cais/mmlu

Category: Reasoning and language understanding benchmarks
[🤗](https://huggingface.co/datasets/cais/mmlu)
[ModelScope](https://modelscope.cn/datasets/cais/mmlu)

### TIGER-Lab/MMLU-Pro

Category: Reasoning and language understanding benchmarks

[🤗](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro)
[ModelScope](https://modelscope.cn/datasets/TIGER-Lab/MMLU-Pro)

### cais/hle

Category: Reasoning and language understanding benchmarks

[🤗](https://huggingface.co/datasets/cais/hle)
[ModelScope](https://modelscope.cn/datasets/cais/hle)

### HumanEval: Hand-Written Evaluation Set

Category: Coding

https://github.com/openai/human-eval

### Mostly Basic Programming Problems (MBPP)

Category: Coding

[🤗](https://huggingface.co/datasets/google-research-datasets/mbpp)
[ModelScope](https://modelscope.cn/datasets/google-research-datasets/mbpp)

### SWE-bench

Category: Coding

https://github.com/SWE-bench/SWE-bench

