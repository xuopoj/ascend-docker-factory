ARG BASE_IMAGE
FROM ${BASE_IMAGE}


# Install basic ML Python packages
RUN apt-get update && apt-get install -y vim && rm -rf /var/lib/apt/lists/* && \
    pip install --no-cache-dir \
    pandas==2.0.3 \
    scikit-learn==1.3.0 \
    matplotlib==3.7.2 \
    seaborn==0.12.2 \
    notebook==6.5.4 \
    numpy==1.26.4 \
    ipykernel==6.25.0 networkx dowhy econml uvicorn fastapi

RUN pip install "chronos-forecasting>=2.0.0"
USER ma-user
WORKDIR /home/ma-user

COPY --chown=ma-user:users projects/chronos-project chronos-project
