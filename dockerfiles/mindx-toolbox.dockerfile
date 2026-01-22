# syntax=docker/dockerfile:1
ARG BASE_IMAGE=cann:8.3rc1-910b
FROM ${BASE_IMAGE}

ARG CANN_VERSION=8.3.RC1

USER root

RUN --mount=type=bind,source=packages/${CANN_VERSION},target=/tmp/packages \
    ls -l /tmp && \
    cd /tmp/packages && \
    ./Ascend-mindx-toolbox_*_linux-*.run --install --quiet

# Toolbox env (set directly since set_env.sh has bash-specific syntax)
ENV PATH=${PATH}:/usr/local/Ascend/toolbox/latest/Ascend-DMI/bin
ENV LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/dcmi:/usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64/driver


RUN echo "source /usr/local/Ascend/driver/bin/setenv.bash" >> /etc/bash.bashrc && \
    echo "source /usr/local/Ascend/ascend-toolkit/set_env.sh" >> /etc/bash.bashrc && \
    echo "source /usr/local/Ascend/toolbox/set_env.sh" >> /etc/bash.bashrc && \
    echo "export PATH=${PATH}:/usr/local/Ascend/toolbox/latest/Ascend-DMI/bin" >> /etc/bash.bashrc && \
    echo "export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/dcmi:/usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64/driver" >> /etc/bash.bashrc && \
    echo "source /usr/local/Ascend/driver/bin/setenv.bash" >> /etc/zsh/zshrc && \
    echo "source /usr/local/Ascend/ascend-toolkit/set_env.sh" >> /etc/zsh/zshrc && \
    echo "export PATH=${PATH}:/usr/local/Ascend/toolbox/latest/Ascend-DMI/bin" >> /etc/zsh/zshrc && \
    echo "export LD_LIBRARY_PATH=${LD_LIBRARY_PATH}:/usr/local/dcmi:/usr/local/Ascend/driver/lib64:/usr/local/Ascend/driver/lib64/driver" >> /etc/zsh/zshrc
