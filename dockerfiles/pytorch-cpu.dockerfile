ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG TORCH_VERSION
ARG TORCH_VARIANT
ENV TORCH_DEVICE_BACKEND_AUTOLOAD=0

# Install PyTorch and related packages
RUN pip install --no-cache-dir \
    torch==${TORCH_VERSION}+${TORCH_VARIANT} \
    torchvision \
    torchaudio \
    --index-url https://download.pytorch.org/whl/${TORCH_VARIANT}

# Install common ML packages
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    scikit-learn \
    matplotlib \
    opencv-python-headless

# Verify installation
RUN python -c "import torch; print(f'PyTorch version: {torch.__version__}')"

CMD ["python"]
