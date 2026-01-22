ARG BASE_IMAGE=cann:83rc1-python310
FROM ${BASE_IMAGE}

ARG TORCH_VERSION=2.7.1
ARG TORCH_NPU_VERSION=2.7.1
ARG TORCHVISION_VERSION=0.20.1

USER ma-user

# Install Python packages (uses global pip config from base image)
RUN pip install --no-cache-dir attrs cython numpy==1.26.4 decorator sympy cffi pyyaml \
    pathlib2 psutil protobuf==3.20 scipy requests absl-py pyyaml wheel typing_extensions \
    tensorboard matplotlib ipykernel "transformers>=4.41,<5"
    
RUN pip install --no-cache-dir datasets tiktoken wandb tqdm libcst

# install pytorch
RUN pip install --no-cache-dir torch==${TORCH_VERSION} torch_npu==${TORCH_NPU_VERSION} torchvision==${TORCHVISION_VERSION}

CMD ["python"]
