import asyncio
import aiohttp
import json
import time
import numpy as np
import os
import urllib.request
import random
import argparse
from dataclasses import dataclass
from typing import List

# --- DEFAULT CONSTANTS (Fallbacks) ---
DEFAULT_URL = "http://localhost:8000/v1/chat/completions"
DEFAULT_MODEL = "Qwen/Qwen3-30B-A3B"
DEFAULT_KEY = "EMPTY"
DEFAULT_DATASET_FILE = "alpaca_data.json"

@dataclass
class RequestMetrics:
    request_id: int
    ttft: float         # Time to First Token
    total_time: float   # Total request latency
    tokens_generated: int
    tpot: float         # Time Per Output Token
    tps: float          # Tokens Per Second (Speed)
    prompt_len: int     # Input length
    success: bool
    error: str = ""

def parse_args():
    parser = argparse.ArgumentParser(description="Benchmark LLM Inference (vLLM/OpenAI-compatible)")
    parser.add_argument("--url", type=str, default=DEFAULT_URL, help="API Endpoint URL")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="Model name (must match server)")
    parser.add_argument("--key", type=str, default=DEFAULT_KEY, help="API Key (if required)")
    
    parser.add_argument("--concurrency", type=int, default=20, help="Number of concurrent requests")
    parser.add_argument("--requests", type=int, default=100, help="Total number of requests to run")
    parser.add_argument("--max-tokens", type=int, default=512, help="Max output tokens per request")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (set to negative to disable)")
    
    return parser.parse_args()

def load_dataset():
    """Parses the Alpaca dataset."""
    print(f"Loading prompts from {DEFAULT_DATASET_FILE}...")
    with open(DEFAULT_DATASET_FILE, "r") as f:
        data = json.load(f)
    
    prompts = []
    for item in data:
        if item.get("input"):
            prompts.append(f"{item['instruction']}\n\nContext: {item['input']}")
        else:
            prompts.append(item['instruction'])
            
    print(f"Loaded {len(prompts)} prompts.")
    return prompts

async def benchmark_request(session: aiohttp.ClientSession, req_id: int, prompt: str, args) -> RequestMetrics:
    """Runs a single request using CLI args."""
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "max_tokens": args.max_tokens,
    }
    headers = {"Authorization": f"Bearer {args.key}"}

    start_time = time.perf_counter()
    ttft = 0.0
    first_token_received = False
    token_count = 0
    
    try:
        async with session.post(args.url, json=payload, headers=headers) as response:
            if response.status != 200:
                text = await response.text()
                return RequestMetrics(req_id, 0, 0, 0, 0, 0, len(prompt), False, f"HTTP {response.status}: {text}")

            async for line_bytes in response.content:
                line = line_bytes.decode('utf-8').strip()
                if not line.startswith("data: "):
                    continue
                
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                
                if not first_token_received:
                    ttft = time.perf_counter() - start_time
                    first_token_received = True
                
                try:
                    data = json.loads(data_str)
                    delta = data['choices'][0]['delta']
                    if 'content' in delta and delta['content']:
                        token_count += 1
                except:
                    continue

        end_time = time.perf_counter()
        total_time = end_time - start_time
        
        generation_time = total_time - ttft
        if token_count > 0 and generation_time > 0:
            tpot = generation_time / token_count
            tps = token_count / generation_time
        else:
            tpot = 0
            tps = 0
            
        return RequestMetrics(req_id, ttft, total_time, token_count, tpot, tps, len(prompt), True)

    except Exception as e:
        return RequestMetrics(req_id, 0, 0, 0, 0, 0, len(prompt), False, str(e))

async def main():
    args = parse_args()
    
    if args.seed >= 0:
        random.seed(args.seed)
        
    all_prompts = load_dataset()
    run_prompts = [random.choice(all_prompts) for _ in range(args.requests)]

    print(f"\n--- Starting Benchmark ---")
    print(f"Target: {args.url}")
    print(f"Model:  {args.model}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Total Req:   {args.requests}")
    
    # Warmup
    print("\nWarming up...")
    async with aiohttp.ClientSession() as session:
        await benchmark_request(session, 0, "Hi", args)
    
    print("Running load test...")
    benchmark_start_wall_time = time.perf_counter()
    
    results: List[RequestMetrics] = []
    async with aiohttp.ClientSession() as session:
        for i in range(0, args.requests, args.concurrency):
            batch_prompts = run_prompts[i : i + args.concurrency]
            tasks = [
                benchmark_request(session, i + idx, p, args) 
                for idx, p in enumerate(batch_prompts)
            ]
            batch_results = await asyncio.gather(*tasks)
            results.extend(batch_results)
            print(f"Completed {len(results)}/{args.requests}...")

    wall_time = time.perf_counter() - benchmark_start_wall_time

    # Analysis
    successful = [r for r in results if r.success]
    if not successful:
        print("\nERROR: All requests failed.")
        print(f"Last error: {results[-1].error if results else 'Unknown'}")
        return

    ttfts = [r.ttft * 1000 for r in successful]
    tpots = [r.tpot * 1000 for r in successful]
    latencies = [r.total_time for r in successful]
    tps_per_user = [r.tps for r in successful]
    total_tokens = sum(r.tokens_generated for r in successful)
    
    system_rps = len(successful) / wall_time
    system_token_gen_rate = total_tokens / wall_time

    print(f"\n================ RESULTS ================")
    print(f"Wall Time:      {wall_time:.2f} s")
    print(f"Successful:     {len(successful)} / {args.requests}")
    print(f"Avg Input Len:  {int(np.mean([r.prompt_len for r in successful]))} chars")
    
    print("\n--- System Throughput ---")
    print(f"RPS:            {system_rps:.2f} req/s")
    print(f"Global TPS:     {system_token_gen_rate:.2f} tokens/s")

    print("\n--- Latency (TTFT) ---")
    print(f"  P50: {np.percentile(ttfts, 50):.2f} ms")
    print(f"  P99: {np.percentile(ttfts, 99):.2f} ms")
    
    print("\n--- Gen Speed (Per User) ---")
    print(f"  TPS P50: {np.percentile(tps_per_user, 50):.2f} tokens/s")

if __name__ == "__main__":
    asyncio.run(main())