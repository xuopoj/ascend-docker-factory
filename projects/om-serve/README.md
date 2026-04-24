# OM Serve

Generic Ascend OM model server with FastAPI. Includes a YOLO-specific server with built-in pre/post-processing.

## Images

| Tag | Chip | Base |
|-----|------|------|
| `om-serve:latest-cann83rc1-910b` | 910B | CANN 8.3RC1 |
| `om-serve:latest-cann83rc1-310p` | 310P | CANN 8.3RC1 |

## Start the server

### Without Docker

```bash
# generic
MODEL_PATH=/path/to/model.om INPUT_SHAPE=1,3,640,640 ./start.sh

# yolo
MODEL_PATH=/path/to/best.om \
CLASSES=aeroplane,bicycle,bird,boat,bottle,bus,car,cat,chair,cow,diningtable,dog,horse,motorbike,person,pottedplant,sheep,sofa,train,tvmonitor \
./start.sh yolo
```

### Generic server (`serve.py`)

Accepts any OM model. Returns raw float32 binary output with shape info in headers.

```bash
docker run -d \
  --device /dev/davinci0 \
  --device /dev/davinci_manager \
  --device /dev/devmm_svm \
  --device /dev/hisi_hdc \
  -e MODEL_PATH=/models/model.om \
  -e INPUT_SHAPE=1,3,640,640 \
  -e DEVICE_ID=0 \
  -v /path/to/models:/models \
  -p 8000:8000 \
  om-serve:latest-cann83rc1-910b
```

### YOLO server (`yolo_serve.py`)

YOLO-specific server. Returns JSON detections with bounding boxes, labels, and confidence scores.

```bash
docker run -d \
  --device /dev/davinci0 \
  --device /dev/davinci_manager \
  --device /dev/devmm_svm \
  --device /dev/hisi_hdc \
  -e MODEL_PATH=/models/best.om \
  -e INPUT_SHAPE=1,3,640,640 \
  -e DEVICE_ID=0 \
  -e CLASSES=aeroplane,bicycle,bird,boat,bottle,bus,car,cat,chair,cow,diningtable,dog,horse,motorbike,person,pottedplant,sheep,sofa,train,tvmonitor \
  -v /path/to/models:/models \
  -p 8000:8000 \
  om-serve:latest-cann83rc1-910b \
  uvicorn yolo_serve:app --host 0.0.0.0 --port 8000
```

## Making requests

### Health check

```bash
curl http://localhost:8000/health
```

### Infer (YOLO server)

```bash
curl -X POST http://localhost:8000/infer \
  -F "image=@photo.jpg"
```

Response:

```json
{
  "detections": [
    {
      "label": "person",
      "class_id": 14,
      "confidence": 0.87,
      "box": { "x1": 120.0, "y1": 45.0, "x2": 280.0, "y2": 390.0 }
    }
  ],
  "count": 1
}
```

Optional query params:

```bash
# adjust confidence and IoU thresholds
curl -X POST "http://localhost:8000/infer?conf=0.5&iou=0.4" \
  -F "image=@photo.jpg"
```

### Infer (generic server)

```bash
# image upload
curl -X POST http://localhost:8000/infer \
  -F "image=@photo.jpg" \
  --output result.bin

# raw float32 tensor
curl -X POST http://localhost:8000/infer \
  -H "Content-Type: application/octet-stream" \
  -H "x-input-shape: 1,3,640,640" \
  --data-binary @tensor.bin \
  --output result.bin
```

Parse output:

```python
import numpy as np

data = open("result.bin", "rb").read()
arr = np.frombuffer(data, dtype=np.float32)
print(arr.shape)
```
