# LLaMA-Factory LLM fine-tuning image for Ascend NPU. ModelArts-compatible (ma-user).
#
# Thin layer over the Ascend-maintained LLaMA-Factory image. Unlike yolo/ and
# nanochat/, this does NOT re-pin torch / torch_npu: the upstream base is built
# and tested against real hardware, and re-pinning that stack blind produces an
# image that imports but cannot see a device. CANN, torch and torch_npu all come
# from the base deliberately.
#
# [untested] No NPU was available when this was written. `docker build` is
# verifiable; the runtime claims below are not.

ARG BASE_IMAGE=quay.io/ascend/llamafactory:0.9.5-npu-a3
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root

# ModelArts runs containers as ma-user (uid 1000, gid 100). Some Ascend bases
# ship it, some don't, so create it only when absent. No `|| true`: if uid 1000
# belongs to another account we want a loud failure here, not a uid mismatch
# that surfaces later as permission-denied on a mounted volume.
RUN if ! getent passwd ma-user >/dev/null; then \
      useradd -m -d /home/ma-user -s /bin/bash -g 100 -u 1000 ma-user; \
    else \
      echo "ma-user present in base image; reusing"; \
    fi

# Writable dirs the container owns. The weights mount point is created but left
# empty — the platform mounts over it read-only at run time.
RUN mkdir -p /home/ma-user/.cache/huggingface \
             /home/ma-user/output \
             /home/ma-user/work/models \
 && chown -R 1000:100 /home/ma-user

USER ma-user
WORKDIR /home/ma-user

# The target NPU box has no route out, so every pip install must succeed HERE.
#
# Defaults to upstream PyPI rather than the Tsinghua mirror used by
# dockerfiles/python.dockerfile: that mirror answered 403 Forbidden from the
# build network (pypi.org answered 200), and a 403 surfaces through pip as the
# thoroughly misleading "from versions: none" — i.e. it reads as a bad version
# pin rather than a blocked index. Pass a mirror explicitly when building from a
# network that needs one:
#   --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple
#
# Passed per-RUN via ARG, NOT set as ENV: a persistent PIP_INDEX_URL would
# survive into the runtime image and point an air-gapped box at an index it
# cannot reach, turning a clear "no network" into a confusing timeout.
ARG PIP_INDEX_URL=https://pypi.org/simple

# Weights come from a READ-ONLY mount, so HF_HOME must NOT point there: the
# huggingface cache writes lock files and metadata even when it downloads
# nothing, and a read-only HF_HOME fails with errors that never mention
# permissions. Keep them separate:
#   OBS_MODELS_DIR - read-only, mounted at run time, holds the weights
#   HF_HOME        - writable local disk, for locks/metadata only
#   OUTPUT_DIR     - writable local disk; sync to OBS after training, not during
#                    (fuse writes are slow enough to stall a training step)
ENV OBS_MODELS_DIR=/home/ma-user/work/models \
    HF_HOME=/home/ma-user/.cache/huggingface \
    HF_HUB_OFFLINE=1 \
    OUTPUT_DIR=/home/ma-user/output \
    PYTHONUNBUFFERED=1 \
    PATH=/home/ma-user/.local/bin:$PATH

# Notebook kernel, so this image can back a ModelArts notebook. `pip install
# ipykernel` alone gives the package but no selectable kernel — the
# `ipykernel install` step registers it in the picker. JupyterLab is omitted:
# ModelArts provides its own.
ARG IPYKERNEL_VERSION=6.29.5
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" "ipykernel==${IPYKERNEL_VERSION}" \
 && python -m ipykernel install --user \
      --name llama-factory-npu --display-name "LLaMA-Factory (Ascend NPU)"

# Deps the base does not ship. Verified absent from 0.9.5-npu-a3 before adding;
# the target box has NO network, so anything missing here cannot be recovered at
# run time.
#
#   tensorboard   - the experiment tracker the configs report to
#   bitsandbytes  - REQUIRED by npu-a3-qlora.yaml (quantization_method: bnb).
#                   Absent from the base, so without it QLoRA fails on an
#                   air-gapped box with a bare ModuleNotFoundError.
#
# Deliberately NOT installed: modelscope (1.37.1) and datasets (4.0.0) already
# ship in the base. Re-pinning them would only risk disturbing a stack upstream
# tested on real hardware.
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
      tensorboard \
      bitsandbytes

# Configs and baked-in datasets. Paths are relative to the REPO ROOT — this
# repo builds every project with `context: .` (see dockerfile-compose.yaml).
# COPY --chown avoids a second chown layer duplicating every file.
COPY --chown=1000:100 projects/llama-factory/configs/ /home/ma-user/llama-factory/configs/
COPY --chown=1000:100 projects/llama-factory/data/     /home/ma-user/llama-factory/data/

# Datasets are baked in deliberately: an NPU box may sit on a network where
# Hugging Face is slow or unreachable, and a run that dies 40 minutes in on a
# dataset fetch wastes the session. Only the 3 datasets the shipped configs
# reference are included; dataset_info.json is trimmed to match, since
# LLaMA-Factory validates every registered entry.

# Devices are passed at `docker run` time (--device /dev/davinci*) along with
# the host driver mounts; nothing device-specific is baked in.

# NO HEALTHCHECK, deliberately.
#
# Measured on this base (0.9.5-npu-a3, arm64, no device attached):
#   - `import torch` / `llamafactory-cli` FAIL with "Failed to load the backend
#     extension: torch_npu", because torch_npu wants the host driver.
#   - With TORCH_DEVICE_BACKEND_AUTOLOAD=0, `import llamafactory` SUCCEEDS
#     (returns 0.9.5) and bitsandbytes imports fine.
#
# So a healthcheck is possible off-device, but only by disabling the very
# backend load that determines whether this image can train — it would go green
# on a box with no usable NPU. A check that cannot fail for the reason you care
# about is worse than none. Readiness is the runbook sequence in README.md, run
# by a human against real hardware.

CMD ["python"]
