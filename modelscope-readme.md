---
license: Apache License 2.0
task: other
tags:
- docker
- ascend
- npu
- vllm
---

# 昇腾 NPU 预构建镜像 / Ascend NPU Pre-built Images

预构建的昇腾 NPU Docker 镜像，适用于训练、推理等场景，免去从头配置环境的麻烦。

> **在线浏览**: [Ascend Image Hub](https://tools.service-delivery-hub.com/ascend-image-hub)
> **镜像仓库 (quay.io)**: `quay.io/service-delivery-hub/`

---

## 可用镜像 / Available Images

### Python 基础镜像

包含 Python 环境、常用工具、oh-my-zsh 及 Jupyter，适配 ModelArts `ma-user`（uid=1000）。

| 版本 | quay.io 标签 | 下载 |
|------|-------------|------|
| 3.10 | `quay.io/service-delivery-hub/python:3.10` | [python-3.10.tar.gz](python/python-3.10.tar.gz) |
| 3.11 | `quay.io/service-delivery-hub/python:3.11` | [python-3.11.tar.gz](python/python-3.11.tar.gz) |

### CANN 镜像

基于 Python 基础镜像，安装 CANN Toolkit + Kernels + NNAL，支持 910B / 310P 芯片。

| 版本 | quay.io 标签 | 下载 |
|------|-------------|------|
| 8.3rc1-910b | `quay.io/service-delivery-hub/cann:8.3rc1-910b` | [cann-8.3rc1-910b.tar.gz](cann/cann-8.3rc1-910b.tar.gz) |
| 8.3rc1-310p | `quay.io/service-delivery-hub/cann:8.3rc1-310p` | [cann-8.3rc1-310p.tar.gz](cann/cann-8.3rc1-310p.tar.gz) |

### PyTorch NPU 镜像

基于 CANN 镜像，安装 PyTorch + torch_npu + torchvision。

| 版本 | quay.io 标签 | 下载 |
|------|-------------|------|
| 2.5.1-cann83rc1-910b | `quay.io/service-delivery-hub/pytorch:2.5.1-cann83rc1-910b` | [pytorch-npu-910b.tar.gz](pytorch-npu/pytorch-npu-910b.tar.gz) |

### YOLO Ascend

基于 [xuopoj/ultralytics](https://github.com/xuopoj/ultralytics/tree/ascend) ascend 分支的目标检测镜像，支持昇腾 NPU 训练推理。

| 版本 | quay.io 标签 | 下载 |
|------|-------------|------|
| latest-torch251-cann83rc1-910b | `quay.io/service-delivery-hub/yolo-ascend:latest-torch251-cann83rc1-910b` | [yolo-ascend.tar.gz](yolo-ascend/yolo-ascend.tar.gz) |

### LLaMA-Factory

基于昇腾官方维护的 [llamafactory](https://quay.io/repository/ascend/llamafactory) 镜像，用于大模型微调（LoRA / QLoRA）。在官方基础镜像之上补充了：

- **bitsandbytes** — QLoRA 必需，官方基础镜像中并未预装
- **tensorboard** — 训练指标记录
- **ModelArts notebook kernel** — 可直接作为 notebook 镜像使用
- **内置演示数据集** — identity + alpaca 中英文（共 2,090 条），适配无外网环境

> ⚠️ **尚未在真实硬件上验证 / NOT YET VALIDATED ON HARDWARE**
> 镜像构建与离线加载已验证（数据集可在 `--network none` 下正常加载），但尚未在真实昇腾 NPU 上完成训练验证。请先在自己的设备上确认后再用于正式任务。

CANN / torch / torch_npu 全部来自官方基础镜像，**未做任何重新固定版本**——官方镜像已在真实硬件上测试过，盲目重新固定版本容易得到"能 import 但看不到设备"的镜像。

| 版本 | quay.io 标签 | 下载 |
|------|-------------|------|
| 0.9.5-npu-a3 | `quay.io/service-delivery-hub/llama-factory:0.9.5-npu-a3` | 暂未上传（见下方说明） |

> 📦 tar.gz 离线包尚未上传至 ModelScope，请暂时使用方式一从 quay.io 拉取，或在联网机器上自行 `docker save` 后传输。

微调配置已内置于 `/home/ma-user/llama-factory/configs/`，权重需通过只读挂载提供（镜像内设置了 `HF_HUB_OFFLINE=1`）：

```bash
llamafactory-cli train /home/ma-user/llama-factory/configs/npu-a3-lora.yaml
```

### vLLM Ascend

基于 [vllm-project/vllm-ascend](https://github.com/vllm-project/vllm-ascend) 的高性能 LLM 推理镜像，已预装网络调试工具。

| 版本 | quay.io 标签 | 下载 |
|------|-------------|------|
| v0.13.0 | `quay.io/service-delivery-hub/vllm-ascend:v0.13.0` | [vllm-ascend-v0.13.0.tar.gz](vllm-ascend/vllm-ascend-v0.13.0.tar.gz) |
| v0.14.0rc1 | `quay.io/service-delivery-hub/vllm-ascend:v0.14.0rc1` | [vllm-ascend-v0.14.0rc1.tar.gz](vllm-ascend/vllm-ascend-v0.14.0rc1.tar.gz) |
| v0.15.0rc1 | `quay.io/service-delivery-hub/vllm-ascend:v0.15.0rc1` | [vllm-ascend-v0.15.0rc1.tar.gz](vllm-ascend/vllm-ascend-v0.15.0rc1.tar.gz) |
| v0.17.0rc1 | `quay.io/service-delivery-hub/vllm-ascend:v0.17.0rc1` | [vllm-ascend-v0.17.0rc1.tar.gz](vllm-ascend/vllm-ascend-v0.17.0rc1.tar.gz) |
| v0.17.0rc1-a3 | `quay.io/service-delivery-hub/vllm-ascend:v0.17.0rc1-a3` | [vllm-ascend-v0.17.0rc1-a3.tar.gz](vllm-ascend/vllm-ascend-v0.17.0rc1-a3.tar.gz) |
| v0.18.0rc1 | `quay.io/service-delivery-hub/vllm-ascend:v0.18.0rc1` | [vllm-ascend-v0.18.0rc1.tar.gz](vllm-ascend/vllm-ascend-v0.18.0rc1.tar.gz) |
| v0.18.0rc1-a3 | `quay.io/service-delivery-hub/vllm-ascend:v0.18.0rc1-a3` | [vllm-ascend-v0.18.0rc1-a3.tar.gz](vllm-ascend/vllm-ascend-v0.18.0rc1-a3.tar.gz) |

---

## 使用方式 / How to Use

### 方式一：直接从 quay.io 拉取（需要网络）

```bash
docker pull quay.io/service-delivery-hub/vllm-ascend:v0.15.0rc1
```

在 Dockerfile 中使用：

```dockerfile
FROM quay.io/service-delivery-hub/vllm-ascend:v0.15.0rc1
```

### 方式二：从 ModelScope 下载 tar.gz（适合离线/内网环境）

1. 在本页面点击对应版本的下载链接，下载 `.tar.gz` 文件
2. 将文件传输到目标机器
3. 导入镜像：

```bash
docker load < vllm-ascend-v0.15.0rc1.tar.gz
```

### 方式三：推送到华为云 SWR（私有云环境）

适用于需要将镜像同步到华为私有云 SWR 仓库的场景。

**第一步：登录 SWR**

登录命令可在 SWR 控制台获取：**容器镜像服务 → 我的镜像 → 右上角「登录指令」**

```bash
docker login -u <用户名> -p <密码> <swr-registry>
```

> 登录命令可在 SWR 控制台获取：**容器镜像服务 → 我的镜像 → 右上角「登录指令」**

**第二步：加载并推送镜像**

```bash
# 加载本地 tar.gz
docker load < vllm-ascend-v0.15.0rc1.tar.gz

# 重新打标签
docker tag quay.io/service-delivery-hub/vllm-ascend:v0.15.0rc1 \
  <swr-registry>/<组织名>/vllm-ascend:v0.15.0rc1

# 推送
docker push <swr-registry>/<组织名>/vllm-ascend:v0.15.0rc1
```

---

## 镜像说明 / Image Notes

- 已创建 `ma-user`（uid=1000）作为默认用户，与昇腾 ModelArts 平台兼容
- 构建脚本开源：[ascend-docker-factory](https://github.com/xuopoj/ascend-docker-factory)
