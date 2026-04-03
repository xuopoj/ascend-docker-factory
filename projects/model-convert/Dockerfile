ARG BASE_IMAGE=quay.io/service-delivery-hub/cann:8.5.0-910b
FROM ${BASE_IMAGE}

USER ma-user

# PyTorch CPU-only for .pt -> .onnx (no NPU needed for export)
# onnx + onnxsim for graph inspection and simplification before ATC
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && \
    pip install --no-cache-dir onnx onnx-simplifier

COPY --chown=ma-user:ma-user projects/model-convert/convert.py /home/ma-user/convert.py
RUN ln -s /home/ma-user/convert.py /home/ma-user/.local/bin/convert

WORKDIR /home/ma-user
CMD ["python", "/home/ma-user/convert.py", "--help"]
