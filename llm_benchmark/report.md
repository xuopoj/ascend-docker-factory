## log-1121-01

4 Ascend 910B3 NPUs

Model:  Qwen/Qwen3-30B-A3B
Concurrency: 5
Total Req:   100

================ RESULTS ================
Wall Time:      1432.30 s
Successful:     100 / 100
Avg Input Len:  85 chars

--- System Throughput ---
RPS:            0.07 req/s
Global TPS:     34.97 tokens/s

--- Latency (TTFT) ---
  P50: 352.10 ms
  P99: 477.07 ms

--- Gen Speed (Per User) ---
  TPS P50: 7.20 tokens/s

## log-1121-02

4 Ascend 910B3 NPUs

--- Starting Benchmark ---
Model:  Qwen/Qwen3-30B-A3B
Concurrency: 100
Total Req:   100

================ RESULTS ================
Wall Time:      101.00 s
Successful:     100 / 100
Avg Input Len:  85 chars

--- System Throughput ---
RPS:            0.99 req/s
Global TPS:     489.19 tokens/s

--- Latency (TTFT) ---
  P50: 2410.49 ms
  P99: 2417.41 ms

--- Gen Speed (Per User) ---
  TPS P50: 5.19 tokens/s

## log-1126-01

1 Ascend 910B3 NPU

Model:  Qwen/Qwen3-1.7B
Concurrency: 20
Total Req:   100

================ RESULTS ================
Wall Time:      141.91 s
Successful:     100 / 100
Avg Input Len:  85 chars

--- System Throughput ---
RPS:            0.70 req/s
Global TPS:     343.44 tokens/s

--- Latency (TTFT) ---
  P50: 483.96 ms
  P99: 497.03 ms

--- Gen Speed (Per User) ---
  TPS P50: 18.35 tokens/s

## log-1126-02

1 Ascend 910B3 NPU

--- Starting Benchmark ---
Target: http://localhost:8000/v1/chat/completions
Model:  Qwen/Qwen3-1.7B
Concurrency: 1
Total Req:   100

================ RESULTS ================
Wall Time:      1910.83 s
Successful:     100 / 100
Avg Input Len:  85 chars

--- System Throughput ---
RPS:            0.05 req/s
Global TPS:     25.91 tokens/s

--- Latency (TTFT) ---
  P50: 97.99 ms
  P99: 110.06 ms

--- Gen Speed (Per User) ---
  TPS P50: 26.07 tokens/s