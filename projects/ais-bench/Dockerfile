# AIS-Bench LLM performance-benchmark CLIENT image (CPU-only).
# Perf mode is a pure HTTP client; the NPU lives on the serving side.
# Adapted from the official docker/ubuntu/Dockerfile.py310.ubuntu22.04.
FROM ubuntu:22.04 AS builder

ARG GIT_TAG=latest
ARG PIP_INDEX_URL=https://repo.huaweicloud.com/repository/pypi/simple
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

RUN if [ "$(uname -m)" = "x86_64" ]; then MIRROR=ubuntu; else MIRROR=ubuntu-ports; fi && \
    : > /etc/apt/sources.list && \
    for s in "jammy" "jammy-updates" "jammy-security" "jammy-backports"; do \
        echo "deb http://repo.huaweicloud.com/${MIRROR}/ ${s} main restricted universe multiverse" >> /etc/apt/sources.list; \
    done && \
    apt-get update && apt-get install -y --no-install-recommends \
        git curl wget unzip ca-certificates \
        python3.10 python3.10-dev python3.10-venv python3.10-distutils python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN pip3 config set global.index-url ${PIP_INDEX_URL} && \
    pip3 config set global.trusted-host $(echo ${PIP_INDEX_URL} | awk -F/ '{print $3}')

RUN git clone --depth 1 https://github.com/AISBench/benchmark.git /benchmark
WORKDIR /benchmark
RUN if [ "$GIT_TAG" != "latest" ]; then \
        git fetch --tags && git checkout "tags/$GIT_TAG" -b "$GIT_TAG-branch"; \
    fi

# CPU-only torch (no CUDA); pull from PyTorch CPU index to avoid mirror hash issues.
RUN pip3 install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# AIS-Bench deps + tokenizer backends. sentencepiece fixes the slow->fast
# tokenizer conversion gap for models that ship only tokenizer.model.
RUN for r in requirements/runtime.txt requirements/api.txt requirements/extra.txt; do \
        if [ -f "$r" ]; then pip3 install --no-cache-dir -r "$r" --use-pep517; fi; \
    done && \
    pip3 install --no-cache-dir sentencepiece rouge_chinese nltk==3.8

RUN pip3 install --no-cache-dir -e ./ --use-pep517

# Offline NLTK punkt so tokenization works without network at run time.
RUN curl -fsSL -o /tmp/punkt.zip https://aisbench.obs.cn-north-4.myhuaweicloud.com/images/benchmark/dependencies/punkt.zip && \
    mkdir -p /usr/share/nltk_data/tokenizers && \
    unzip -q /tmp/punkt.zip -d /usr/share/nltk_data/tokenizers && \
    rm /tmp/punkt.zip

# ---- runtime stage ----
FROM ubuntu:22.04

ARG TTYD_VERSION=1.7.7
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV NLTK_DATA=/usr/share/nltk_data
ENV PATH=/usr/local/bin:$PATH

RUN if [ "$(uname -m)" = "x86_64" ]; then MIRROR=ubuntu; else MIRROR=ubuntu-ports; fi && \
    : > /etc/apt/sources.list && \
    for s in "jammy" "jammy-updates" "jammy-security" "jammy-backports"; do \
        echo "deb http://repo.huaweicloud.com/${MIRROR}/ ${s} main restricted universe multiverse" >> /etc/apt/sources.list; \
    done && \
    apt-get update && apt-get install -y --no-install-recommends \
        curl vim git ca-certificates \
        python3.10 python3.10-dev python3.10-venv python3.10-distutils python3-pip && \
    apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# ttyd: web-based terminal over HTTP (aarch64).
# Prefer a vendored binary from the build context (projects/ais-bench/vendor/);
# fall back to downloading from GitHub / mirrors if it's absent. The vendored
# path makes builds deterministic in networks where the BuildKit daemon can't
# reach GitHub's TLS endpoints.
COPY projects/ais-bench/vendor/ /tmp/ttyd-vendor/
RUN set -e; \
    if [ -f /tmp/ttyd-vendor/ttyd.aarch64 ]; then \
        cp /tmp/ttyd-vendor/ttyd.aarch64 /usr/local/bin/ttyd; \
    else \
        for u in \
            "https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.aarch64" \
            "https://gh-proxy.com/https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.aarch64" \
            "https://ghfast.top/https://github.com/tsl0922/ttyd/releases/download/${TTYD_VERSION}/ttyd.aarch64"; do \
            echo "Fetching ttyd from $u"; \
            if curl -fSL --retry 5 --retry-all-errors --retry-delay 2 --connect-timeout 15 -o /usr/local/bin/ttyd "$u"; then break; fi; \
        done; \
    fi; \
    test -s /usr/local/bin/ttyd; \
    chmod +x /usr/local/bin/ttyd; \
    rm -rf /tmp/ttyd-vendor

COPY --from=builder /usr/local/lib/python3.10 /usr/local/lib/python3.10
COPY --from=builder /usr/local/bin /usr/local/bin
COPY --from=builder /usr/lib/python3/dist-packages /usr/lib/python3/dist-packages
COPY --from=builder /benchmark /benchmark
COPY --from=builder /usr/share/nltk_data /usr/share/nltk_data

# Bench helpers (relative to build context = repo root).
COPY projects/ais-bench/sitecustomize.py /opt/ais-bench/sitecustomize.py
COPY projects/ais-bench/run_bench.sh /usr/local/bin/run_bench.sh
COPY projects/ais-bench/configs/perf_template.py /opt/ais-bench/perf_template.py
RUN chmod +x /usr/local/bin/run_bench.sh

ENV PYTHONPATH=/opt/ais-bench
WORKDIR /benchmark
EXPOSE 7681
CMD ["ttyd", "--writable", "bash"]
