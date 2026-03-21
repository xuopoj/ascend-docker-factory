ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

ARG PYTHON_VERSION=3.10
ARG PIP_INDEX_URL=https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
ARG INCLUDE_DEBUG_TOOLS=true

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Install essential system dependencies and Python
RUN apt-get update && apt-get upgrade -y && apt-get install -y \
    software-properties-common \
    zsh \
    wget \
    curl \
    git \
    build-essential \
    ca-certificates \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y \
    python${PYTHON_VERSION} \
    python${PYTHON_VERSION}-dev \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python${PYTHON_VERSION} \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python \
    && ln -sf /usr/bin/python${PYTHON_VERSION} /usr/bin/python3 \
    && rm -rf /var/lib/apt/lists/*

# Verify Python installation
RUN python --version && pip --version

# Install network debugging tools (optional)
RUN if [ "$INCLUDE_DEBUG_TOOLS" = "true" ]; then \
    apt-get update && apt-get install -y \
        net-tools \
        iputils-ping \
        telnet \
        vim \
        netcat-openbsd \
        nmap \
        traceroute \
        dnsutils \
        sudo \
        && rm -rf /var/lib/apt/lists/*; \
    fi


# Install oh-my-zsh for root
RUN sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended

# Copy oh-my-zsh to /etc/skel for new users
RUN cp -r /root/.oh-my-zsh /etc/skel/ && \
    cp /root/.zshrc /etc/skel/ && \
    chsh -s /bin/zsh root

RUN useradd -m -d /home/ma-user -s /bin/zsh -g 100 -u 1000 ma-user

# Configure sudo to not require password for ma-user
RUN echo "ma-user ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/ma-user && \
    chmod 0440 /etc/sudoers.d/ma-user

USER ma-user

# Configure pip mirror globally
RUN pip config set global.index-url ${PIP_INDEX_URL} && \
    pip config set global.timeout 600

# Install common Python packages
RUN pip install --no-cache-dir \
    pip \
    setuptools \
    wheel \
    requests \
    pyyaml

WORKDIR /home/ma-user

RUN pip install --no-cache-dir jupyter_core==5.7.2 jupyter_client==8.6.3 ipython==8.10.0 ipykernel==6.29.5

RUN python3 -m ipykernel install --user --name "python${PYTHON_VERSION}" && \
    rm -r /home/ma-user/.local/share/jupyter/kernels/python${PYTHON_VERSION}/logo-*

CMD ["python"]
