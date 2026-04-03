ARG BASE_IMAGE=quay.io/service-delivery-hub/pytorch:2.9.0-cann850-910b
FROM ${BASE_IMAGE}

ARG TORCH_VERSION=2.9.0
ARG TORCH_NPU_VERSION=2.9.0
ARG TORCHVISION_VERSION=0.24.0

USER ma-user

# Clone nanochat ascend fork in editable mode
RUN git clone -b ascend https://github.com/xuopoj/nanochat.git /home/ma-user/xuopoj/nanochat && \
    pip install --no-cache-dir -e /home/ma-user/xuopoj/nanochat && \
    pip install --no-cache-dir --force-reinstall torch==${TORCH_VERSION} torchvision==${TORCHVISION_VERSION} && \
    pip install --no-cache-dir --no-deps torch_npu==${TORCH_NPU_VERSION} && \
    # Pre-cache tiktoken encodings so tok_eval works offline
    python -c "import tiktoken; tiktoken.get_encoding('gpt2'); tiktoken.get_encoding('cl100k_base')"

WORKDIR /home/ma-user
CMD ["python"]
