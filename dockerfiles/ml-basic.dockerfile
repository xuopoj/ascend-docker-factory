ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Install system dependencies for ML libraries
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    libblas-dev \
    liblapack-dev \
    gfortran \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Install basic ML Python packages
RUN pip install --no-cache-dir \
    numpy==1.24.3 \
    pandas==2.0.3 \
    scikit-learn==1.3.0 \
    matplotlib==3.7.2 \
    seaborn==0.12.2 \
    notebook==6.5.4 \
    ipykernel==6.25.0


CMD ["bash"]
