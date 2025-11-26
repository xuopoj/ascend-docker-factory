ARG BASE_IMAGE=v0.11.0rc2

FROM quay.io/ascend/vllm-ascend:${BASE_IMAGE}

RUN apt-get update && apt-get install -y \
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
    bandwhich \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -d /home/ma-user -s /bin/bash -g 100 -u 1000 ma-user
USER ma-user
WORKDIR /home/ma-user

RUN pip install aiohttp numpy

COPY --chown=ma-user:users llm_benchmark/ llm_benchmark/
