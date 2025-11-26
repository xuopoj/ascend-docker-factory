ARG BASE_IMAGE
FROM ${BASE_IMAGE}

# Install YOLOv11 and dependencies
RUN pip install --no-cache-dir \
    ultralytics \
    opencv-python-headless \
    pillow

# Create app directory
WORKDIR /app

# Default command
CMD ["python", "-c", "from ultralytics import YOLO; print('YOLO ready!')"]