# LLaMA-Factory fine-tuning image for Ascend NPU (ModelArts ma-user).
# Thin layer over the Ascend-maintained base; CANN/torch/torch_npu come from it
# untouched. See README.md for the reasoning behind every choice here.

ARG BASE_IMAGE=quay.io/ascend/llamafactory:0.9.5-npu-a3
FROM ${BASE_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

USER root

# No `|| true`: a uid 1000 collision must fail the build, not surface later.
RUN if ! getent passwd ma-user >/dev/null; then \
      useradd -m -d /home/ma-user -s /bin/bash -g 100 -u 1000 ma-user; \
    else \
      echo "ma-user present in base image; reusing"; \
    fi

RUN mkdir -p /home/ma-user/.cache/huggingface \
             /home/ma-user/output \
             /home/ma-user/work/models \
 && chown -R 1000:100 /home/ma-user

USER ma-user
WORKDIR /home/ma-user

# ARG, not ENV: a persisted index URL breaks the air-gapped target box.
ARG PIP_INDEX_URL=https://pypi.org/simple

# HF_HOME must not be the read-only weights mount.
ENV OBS_MODELS_DIR=/home/ma-user/work/models \
    HF_HOME=/home/ma-user/.cache/huggingface \
    HF_HUB_OFFLINE=1 \
    OUTPUT_DIR=/home/ma-user/output \
    PYTHONUNBUFFERED=1 \
    PATH=/home/ma-user/.local/bin:$PATH

ARG IPYKERNEL_VERSION=6.29.5
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" "ipykernel==${IPYKERNEL_VERSION}" \
 && python -m ipykernel install --user \
      --name llama-factory-npu --display-name "LLaMA-Factory (Ascend NPU)"

# bitsandbytes is required by npu-a3-qlora.yaml and absent from the base.
RUN pip install --no-cache-dir --index-url "${PIP_INDEX_URL}" \
      tensorboard \
      bitsandbytes

COPY --chown=1000:100 projects/llama-factory/configs/ /home/ma-user/llama-factory/configs/
COPY --chown=1000:100 projects/llama-factory/data/     /home/ma-user/llama-factory/data/

# No HEALTHCHECK: any device check is red off-device and green on a box with no
# usable NPU. See README.md.

CMD ["python"]
