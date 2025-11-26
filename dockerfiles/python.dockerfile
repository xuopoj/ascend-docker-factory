ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

ARG PYTHON_VERSION

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install system dependencies and Python
RUN apt-get update && apt-get install -y \
    software-properties-common \
    wget \
    curl \
    git \
    build-essential \
    ca-certificates \
    # Network tools
    net-tools \
    iputils-ping \
    telnet \
    netcat-openbsd \
    nmap \
    traceroute \
    dnsutils \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    python${PYTHON_VERSION}-distutils \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python${PYTHON_VERSION} \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*

# Verify Python installation
RUN python --version && pip --version

# Install common Python packages
RUN pip install --no-cache-dir \
    pip \
    setuptools \
    wheel \
    requests \
    pyyaml

RUN useradd -m -d /home/ma-user -s /bin/bash -g 100 -u 1000 ma-user

ENV DEBIAN_FRONTEND=dialog
CMD ["python"]
