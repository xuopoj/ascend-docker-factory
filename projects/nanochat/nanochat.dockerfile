ARG BASE_IMAGE=quay.io/service-delivery-hub/pytorch:2.9.0-cann850-910b
FROM ${BASE_IMAGE}

USER ma-user

# Clone nanochat ascend fork in editable mode
RUN git clone -b ascend https://github.com/xuopoj/nanochat.git /home/ma-user/xuopoj/nanochat && \
    pip install --no-cache-dir -e /home/ma-user/xuopoj/nanochat && \
    pip install --no-cache-dir --force-reinstall torch==2.9.0 torchvision==0.24.0 && \
    pip install --no-cache-dir --no-deps torch_npu==2.9.0

WORKDIR /home/ma-user
CMD ["python"]
