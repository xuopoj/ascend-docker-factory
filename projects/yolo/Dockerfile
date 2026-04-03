ARG BASE_IMAGE=quay.io/service-delivery-hub/pytorch:2.5.1-cann83rc1-910b
FROM ${BASE_IMAGE}

ARG TORCH_VERSION=2.5.1
ARG TORCH_NPU_VERSION=2.5.1
ARG TORCHVISION_VERSION=0.20.1

USER ma-user

# Clone ascend fork and install in editable mode for on-the-fly editing
RUN git clone -b ascend https://github.com/xuopoj/ultralytics.git /home/ma-user/xuopoj/ultralytics && \
    pip install --no-cache-dir -e /home/ma-user/xuopoj/ultralytics && \
    pip install --no-cache-dir --force-reinstall opencv-python-headless && \
    pip install --no-cache-dir --force-reinstall torch==${TORCH_VERSION} torchvision==${TORCHVISION_VERSION} && \
    pip install --no-cache-dir --no-deps torch_npu==${TORCH_NPU_VERSION} && \
    pip install --no-cache-dir onnx onnxruntime onnxsim onnxslim tensorboard

RUN TORCH_DEVICE_BACKEND_AUTOLOAD=0 /home/ma-user/.local/bin/yolo settings tensorboard=True

WORKDIR /home/ma-user
CMD ["python"]
