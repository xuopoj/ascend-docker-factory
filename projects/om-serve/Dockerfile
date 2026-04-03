ARG BASE_IMAGE=quay.io/service-delivery-hub/cann:8.3rc1-910b
FROM ${BASE_IMAGE}

# Add ACL Python bindings to path
ENV PYTHONPATH=/usr/local/Ascend/ascend-toolkit/latest/python/site-packages:${PYTHONPATH}

USER ma-user

RUN pip install --no-cache-dir fastapi uvicorn "numpy<2" pillow python-multipart

WORKDIR /home/ma-user
COPY projects/om-serve/serve.py .
COPY projects/om-serve/yolo_serve.py .
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8000"]
