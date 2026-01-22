# syntax=docker/dockerfile:1
ARG BASE_IMAGE=python:3.10
FROM ${BASE_IMAGE}

ARG CANN_VERSION=8.3.RC1
ARG CHIP_TYPE="910b"
ARG DRIVER_VERSION="24.1.1"
ARG INSTALL_COMPONENTS=toolkit,nnal,kernels

ENV DEBIAN_FRONTEND=noninteractive

USER root

# 3. Install CANN via BuildKit Mount
RUN --mount=type=bind,source=packages/${CANN_VERSION},target=/tmp/packages \
    cd /tmp/packages && \
    export LD_LIBRARY_PATH="" && \
    export PYTHONPATH="" && \
    export DRIVER_VERSION=24.1.1 && \
    ./Ascend-cann-toolkit_${CANN_VERSION}_linux-*.run --install --quiet && \
    . /usr/local/Ascend/ascend-toolkit/set_env.sh && \
    ./Ascend-cann-kernels-${CHIP_TYPE}_${CANN_VERSION}_linux-*.run --install --quiet && \
    ./Ascend-cann-nnal_${CANN_VERSION}_linux-*.run --install --quiet && \
    echo "CANN installation completed"

# 4. Environment Variables
ENV ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest \
    ASCEND_AICPU_PATH=/usr/local/Ascend/ascend-toolkit/latest \
    ASCEND_OPP_PATH=/usr/local/Ascend/ascend-toolkit/latest/opp \
    TOOLCHAIN_HOME=/usr/local/Ascend/ascend-toolkit/latest/toolkit \
    ASCEND_HOME_PATH=/usr/local/Ascend/ascend-toolkit/latest
ENV LD_LIBRARY_PATH=${ASCEND_TOOLKIT_HOME}/lib64:${ASCEND_TOOLKIT_HOME}/lib64/plugin/opskernel:${ASCEND_TOOLKIT_HOME}/lib64/plugin/nnengine:${ASCEND_TOOLKIT_HOME}/opp/built-in/op_impl/ai_core/tbe/op_tiling/lib/linux/aarch64:${ASCEND_TOOLKIT_HOME}/tools/aml/lib64:${ASCEND_TOOLKIT_HOME}/tools/aml/lib64/plugin:/usr/local/Ascend/driver/lib64/driver
ENV PYTHONPATH=${ASCEND_TOOLKIT_HOME}/python/site-packages:${ASCEND_TOOLKIT_HOME}/opp/built-in/op_impl/ai_core/tbe
ENV PATH=${ASCEND_TOOLKIT_HOME}/bin:${ASCEND_TOOLKIT_HOME}/compiler/ccec_compiler/bin:${ASCEND_TOOLKIT_HOME}/tools/ccec_compiler/bin:${PATH}


# 5. Hardware Metadata Labeling
LABEL com.ascend.chip=${CHIP_TYPE} \
      com.ascend.driver.version=${DRIVER_VERSION} \
      com.ascend.cann.version=${CANN_VERSION}
