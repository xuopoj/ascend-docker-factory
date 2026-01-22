ARG BASE_IMAGE=v0.11.0rc2
ARG INCLUDE_DEBUG_TOOLS=true

FROM quay.io/ascend/vllm-ascend:${BASE_IMAGE}

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
        bandwhich \
        && rm -rf /var/lib/apt/lists/*; \
    fi

RUN useradd -m -d /home/ma-user -s /bin/bash -g 100 -u 1000 ma-user
USER ma-user
WORKDIR /home/ma-user
