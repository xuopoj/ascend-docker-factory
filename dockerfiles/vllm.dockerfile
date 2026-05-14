ARG BASE_IMAGE=v0.13.0rc1
FROM quay.io/ascend/vllm-ascend:${BASE_IMAGE}

ARG INCLUDE_DEBUG_TOOLS=true

# Install debugging and network tools (optional)
RUN if [ "$INCLUDE_DEBUG_TOOLS" = "true" ]; then \
    apt-get update && apt-get install -y \
        curl \
        wget \
        net-tools \
        netstat-nat \
        iperf3 \
        tcpdump \
        htop \
        iotop \
        sysstat \
        procps \
        iputils-ping \
        traceroute \
        nload \
        && rm -rf /var/lib/apt/lists/*; \
    fi

# The base image installs vllm-ascend's prebuilt custom CANN ops (e.g.
# aclnnAddRmsNormBias, used by DeepSeek-V4's RMSNorm + several fusion passes)
# under /vllm-workspace/vllm-ascend/vllm_ascend/_cann_ops_custom with
# 0750 perms owned by root:root. When we switch USER to a non-root ma-user
# below, CANN can no longer dlopen libcust_opapi.so or read the ascend910b
# kernel binaries, which surfaces at first dispatch as:
#     "aclnnAddRmsNormBias op not found"
# Grant others read + directory-traverse (capital X only adds x to dirs,
# leaving regular files' exec bits alone).
RUN chmod -R o+rX /vllm-workspace/vllm-ascend/vllm_ascend/_cann_ops_custom

RUN useradd -m -d /home/ma-user -s /bin/bash -g 100 -u 1000 ma-user
USER ma-user
WORKDIR /home/ma-user
