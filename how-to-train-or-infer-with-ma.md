
# 基于MA的训推[WIP]

### 分布式训练

#### 一机多卡

```bash
cd /home/ma-user/minimind/trainer/ && \
torchrun --nproc_per_node=8 train_pretrain.py --device npu --data_path /home/ma-user/modelarts/inputs/dataset_0/pretrain_hq.jsonl --save_dir /home/ma-user/modelarts/outputs/model_v2_0 --batch_size 128
```

```bash
cd /home/ma-user/minimind/trainer/ && \
torchrun --nproc_per_node=8 train_pretrain.py --device npu --data_path /home/ma-user/modelarts/inputs/dataset_0/pretrain_hq.jsonl --save_dir /home/ma-user/modelarts/outputs/model_v2_0 --batch_size 128
```

#### 多机多卡

```bash
cd /home/ma-user/minimind/trainer/ && \
torchrun --nproc_per_node=4 train_pretrain.py --device npu --data_path /home/ma-user/modelarts/inputs/dataset_0/pretrain_hq.jsonl --save_dir /home/ma-user/modelarts/outputs/model_v2_0 --batch_size 128
```


### 推理

```bash
vllm serve ./model --served-model-name Qwen3-32B --tensor-parallel-size 4 --enable-auto-tool-choice --tool-call-parser hermes --chat-template ./model/qwen3_nonthinking.jinja

vllm serve ./model --served-model-name Qwen3-1_7B-pangu3 --port 8080 --enable-auto-tool-choice --tool-call-parser hermes

```


```http
POST https://172.25.21.229:8001/v1/infers/215f6101-a89a-4821-aadc-4e8c7cf13bee/v1/chat/completions

{ 
    "messages": [ 
      { 
        "role": "user", 
        "content": "请介绍一下苏州。" 
      } 
    ]
}
```


## Minimind

```bash
python train_pretrain.py --device npu --data_path ../../modelarts/inputs/DATASET_0/pretrain_hq.jsonl
torchrun --nproc_per_node=8 train_pretrain.py --device npu --data_path ../../modelarts/inputs/DATASET_0/pretrain_hq.jsonl --batch_size 128
torchrun --nproc_per_node=8 train_full_sft.py --device npu --data_path ../../modelarts/inputs/DATASET_0/sft_mini_512.jsonl --batch_size 64

python eval_llm.py --weight pretrain
```


### 多机推理


#### On Node1
```bash
#!/bin/sh
# this obtained through ifconfig
# nic_name is the network interface name corresponding to local_ip of the current node
nic_name="eth0"
local_ip="172.16.0.77"


# export VLLM_USE_V1=1


export HCCL_IF_IP=$local_ip
export GLOO_SOCKET_IFNAME=$nic_name
export TP_SOCKET_IFNAME=$nic_name
export HCCL_SOCKET_IFNAME=$nic_name
export OMP_PROC_BIND=false
export OMP_NUM_THREADS=100
export HCCL_BUFFSIZE=1024

vllm serve ./modelarts/inputs/Qwen3-VL_0/ \
--host 0.0.0.0 \
--port 8000 \
--data-parallel-size 2 \
--api-server-count 2 \
--data-parallel-size-local 1 \
--data-parallel-address $local_ip \
--data-parallel-rpc-port 13389 \
--seed 1024 \
--served-model-name qwen3vl \
--tensor-parallel-size 8 \
--enable-expert-parallel \
--max-num-seqs 16 \
--max-model-len 4096 \
--max-num-batched-tokens 4096 \
--trust-remote-code \
--no-enable-prefix-caching \
--gpu-memory-utilization 0.8

```


#### On node2

```bash
#!/bin/sh

# this obtained through ifconfig
# nic_name is the network interface name corresponding to local_ip of the current node
nic_name="eth0"
local_ip="172.16.0.58"

# The value of node0_ip must be consistent with the value of local_ip set in node0 (master node)
node0_ip="172.16.0.77"


# export VLLM_USE_V1=1


export HCCL_IF_IP=$local_ip
export GLOO_SOCKET_IFNAME=$nic_name
export TP_SOCKET_IFNAME=$nic_name
export HCCL_SOCKET_IFNAME=$nic_name
export OMP_PROC_BIND=false
export OMP_NUM_THREADS=100
export HCCL_BUFFSIZE=1024

vllm serve ./modelarts/inputs/Qwen3-VL_0/ \
--host 0.0.0.0 \
--port 8000 \
--headless \
--data-parallel-size 2 \
--data-parallel-size-local 1 \
--data-parallel-start-rank 1 \
--data-parallel-address $node0_ip \
--data-parallel-rpc-port 13389 \
--seed 1024 \
--tensor-parallel-size 8 \
--served-model-name qwen3vl \
--max-num-seqs 16 \
--max-model-len 4096 \
--max-num-batched-tokens 4096 \
--enable-expert-parallel \
--trust-remote-code \
--no-enable-prefix-caching \
--gpu-memory-utilization 0.8 

```