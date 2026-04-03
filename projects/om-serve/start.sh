#!/bin/bash
# Usage: ./start.sh [generic|yolo]
# Example:
#   MODEL_PATH=/path/to/model.om ./start.sh
#   MODEL_PATH=/path/to/best.om CLASSES=person,car ./start.sh yolo

export PYTHONPATH=/usr/local/Ascend/ascend-toolkit/latest/python/site-packages:$PYTHONPATH

MODE=${1:-generic}

if [ "$MODE" = "yolo" ]; then
    uvicorn yolo_serve:app --host 0.0.0.0 --port 8000
else
    uvicorn serve:app --host 0.0.0.0 --port 8000
fi
