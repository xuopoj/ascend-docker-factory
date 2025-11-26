ARG BASE_IMAGE
FROM ${BASE_IMAGE}

USER ma-user
WORKDIR /home/ma-user
RUN git clone https://gitee.com/ascend/msit

WORKDIR /home/ma-user/msit
# Optional, this commit has been verified
# RUN git checkout f8ab35a772a6c1ee7675368a2aa4bafba3bedd1a

WORKDIR /home/ma-user/msit/msmodelslim
RUN bash install.sh

WORKDIR /home/ma-user

