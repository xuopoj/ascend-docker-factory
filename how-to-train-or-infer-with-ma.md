
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