# syntax=docker/dockerfile:1
ARG BASE_IMAGE=python:3.10
FROM ${BASE_IMAGE}

ARG CANN_VERSION=8.5.0
ARG CANN_BUILD_TAG=8.5.T63
ARG CHIP_TYPE=910b

ENV DEBIAN_FRONTEND=noninteractive

USER root

RUN wget -q "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN%20${CANN_BUILD_TAG}/Ascend-cann_${CANN_VERSION}_linux-aarch64.run" \
    && bash ./Ascend-cann_${CANN_VERSION}_linux-aarch64.run --install --quiet \
    && rm Ascend-cann_${CANN_VERSION}_linux-aarch64.run \
    && wget -q "https://ascend-repo.obs.cn-east-2.myhuaweicloud.com/CANN/CANN%20${CANN_BUILD_TAG}/Ascend-cann-${CHIP_TYPE}-ops_${CANN_VERSION}_linux-aarch64.run" \
    && bash ./Ascend-cann-${CHIP_TYPE}-ops_${CANN_VERSION}_linux-aarch64.run --install --quiet \
    && rm Ascend-cann-${CHIP_TYPE}-ops_${CANN_VERSION}_linux-aarch64.run

# CANN Toolkit Environment
ENV ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest \
    ASCEND_AICPU_PATH=/usr/local/Ascend/ascend-toolkit/latest \
    ASCEND_OPP_PATH=/usr/local/Ascend/ascend-toolkit/latest/opp \
    TOOLCHAIN_HOME=/usr/local/Ascend/ascend-toolkit/latest/toolkit \
    ASCEND_HOME_PATH=/usr/local/Ascend/ascend-toolkit/latest
ENV LD_LIBRARY_PATH=${ASCEND_TOOLKIT_HOME}/lib64:${ASCEND_TOOLKIT_HOME}/lib64/plugin/opskernel:${ASCEND_TOOLKIT_HOME}/lib64/plugin/nnengine:${ASCEND_TOOLKIT_HOME}/opp/built-in/op_impl/ai_core/tbe/op_tiling/lib/linux/aarch64:${ASCEND_TOOLKIT_HOME}/tools/aml/lib64:${ASCEND_TOOLKIT_HOME}/tools/aml/lib64/plugin
ENV PYTHONPATH=${ASCEND_TOOLKIT_HOME}/python/site-packages:${ASCEND_TOOLKIT_HOME}/opp/built-in/op_impl/ai_core/tbe
ENV PATH=${ASCEND_TOOLKIT_HOME}/bin:${ASCEND_TOOLKIT_HOME}/compiler/ccec_compiler/bin:${ASCEND_TOOLKIT_HOME}/tools/ccec_compiler/bin:${PATH}

# Ascend Driver Environment (host-mounted at runtime via device plugin)
ENV ASCEND_DRIVER_HOME=/usr/local/Ascend/driver
ENV LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:${ASCEND_DRIVER_HOME}/lib64:${ASCEND_DRIVER_HOME}/lib64/driver
ENV PATH=${PATH}:${ASCEND_DRIVER_HOME}/bin

RUN { \
    echo '# CANN Toolkit'; \
    echo 'export ASCEND_TOOLKIT_HOME=/usr/local/Ascend/ascend-toolkit/latest'; \
    echo 'export ASCEND_AICPU_PATH=$ASCEND_TOOLKIT_HOME'; \
    echo 'export ASCEND_OPP_PATH=$ASCEND_TOOLKIT_HOME/opp'; \
    echo 'export TOOLCHAIN_HOME=$ASCEND_TOOLKIT_HOME/toolkit'; \
    echo 'export ASCEND_HOME_PATH=$ASCEND_TOOLKIT_HOME'; \
    echo 'export LD_LIBRARY_PATH=$ASCEND_TOOLKIT_HOME/lib64:$ASCEND_TOOLKIT_HOME/lib64/plugin/opskernel:$ASCEND_TOOLKIT_HOME/lib64/plugin/nnengine:$ASCEND_TOOLKIT_HOME/opp/built-in/op_impl/ai_core/tbe/op_tiling/lib/linux/aarch64:$ASCEND_TOOLKIT_HOME/tools/aml/lib64:$ASCEND_TOOLKIT_HOME/tools/aml/lib64/plugin'; \
    echo 'export PYTHONPATH=$ASCEND_TOOLKIT_HOME/python/site-packages:$ASCEND_TOOLKIT_HOME/opp/built-in/op_impl/ai_core/tbe'; \
    echo ''; \
    echo '# Ascend Driver (host-mounted at runtime)'; \
    echo 'export ASCEND_DRIVER_HOME=/usr/local/Ascend/driver'; \
    echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:$ASCEND_DRIVER_HOME/lib64:$ASCEND_DRIVER_HOME/lib64/driver'; \
    echo ''; \
    echo '# PATH (with dedup guard)'; \
    echo 'case ":$PATH:" in *":$ASCEND_TOOLKIT_HOME/bin:"*) ;; *) export PATH=$ASCEND_TOOLKIT_HOME/bin:$ASCEND_TOOLKIT_HOME/compiler/ccec_compiler/bin:$ASCEND_TOOLKIT_HOME/tools/ccec_compiler/bin:$PATH ;; esac'; \
    echo 'case ":$PATH:" in *":$ASCEND_DRIVER_HOME/bin:"*) ;; *) export PATH=$PATH:$ASCEND_DRIVER_HOME/bin ;; esac'; \
    } > /etc/profile.d/ascend.sh && \
    cp /etc/profile.d/ascend.sh /etc/ascend-env.sh && \
    echo '. /etc/ascend-env.sh' >> /etc/bash.bashrc

LABEL com.ascend.chip=${CHIP_TYPE} \
      com.ascend.cann.version=${CANN_VERSION}
