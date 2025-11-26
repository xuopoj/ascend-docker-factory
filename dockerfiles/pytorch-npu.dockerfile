ARG BASE_IMAGE=xuopoj/cann:8.2rc1-910b
FROM ${BASE_IMAGE}

ARG TORCH_VERSION
ARG TORCH_NPU_VERSION

# Install Python packages
RUN pip install --no-cache-dir attrs cython numpy==1.26.4 decorator sympy cffi pyyaml \
    pathlib2 psutil protobuf==3.20 scipy requests absl-py pyyaml wheel typing_extensions \
    tensorboard matplotlib onnxruntime-cann ipykernel "transformers>=4.41,<5" -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple --default-timeout=600

# install pytorch
RUN pip install --no-cache-dir torch==${TORCH_VERSION} torch_npu==${TORCH_NPU_VERSION} -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple --default-timeout=600

CMD ["python"]
