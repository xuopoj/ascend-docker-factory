"""
YOLO OM model server.
Input: image file
Output: object detection annotations (boxes, labels, scores)

Usage:
    MODEL_PATH=/models/best.om CLASSES=person,car,dog uvicorn yolo_serve:app --host 0.0.0.0 --port 8000
"""
import io
import os
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from PIL import Image

import acl

_context = None
_model_id = None
_model_desc = None
_input_shape = (1, 3, 640, 640)  # default YOLOv8
_classes = []


def init_acl():
    global _context, _model_id, _model_desc, _input_shape, _classes

    model_path = os.environ.get("MODEL_PATH")
    if not model_path:
        raise RuntimeError("MODEL_PATH environment variable not set")

    device_id = int(os.environ.get("DEVICE_ID", "0"))

    shape_str = os.environ.get("INPUT_SHAPE", "1,3,640,640")
    _input_shape = tuple(int(x) for x in shape_str.split(","))

    classes_str = os.environ.get("CLASSES", "")
    _classes = [c.strip() for c in classes_str.split(",")] if classes_str else []

    ret = acl.init()
    assert ret == 0, f"acl.init failed: {ret}"
    ret = acl.rt.set_device(device_id)
    assert ret == 0, f"set_device failed: {ret}"
    _context, ret = acl.rt.create_context(device_id)
    assert ret == 0, f"create_context failed: {ret}"
    _model_id, ret = acl.mdl.load_from_file(model_path)
    assert ret == 0, f"load_from_file failed: {ret}"
    _model_desc = acl.mdl.create_desc()
    ret = acl.mdl.get_desc(_model_desc, _model_id)
    assert ret == 0, f"get_desc failed: {ret}"


def shutdown():
    if _model_desc:
        acl.mdl.destroy_desc(_model_desc)
    if _model_id is not None:
        acl.mdl.unload(_model_id)
    if _context:
        acl.rt.destroy_context(_context)
    acl.rt.reset_device(int(os.environ.get("DEVICE_ID", "0")))
    acl.finalize()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_acl()
    yield
    shutdown()


app = FastAPI(lifespan=lifespan)


def preprocess(image_bytes: bytes) -> tuple[np.ndarray, int, int]:
    _, _, h, w = _input_shape
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = img.size
    img = img.resize((w, h))
    arr = np.array(img, dtype=np.float32) / 255.0
    arr = arr.transpose(2, 0, 1)[np.newaxis, ...]  # BCHW
    return np.ascontiguousarray(arr), orig_w, orig_h


def run_inference(arr: np.ndarray) -> np.ndarray:
    input_dataset = acl.mdl.create_dataset()
    output_dataset = acl.mdl.create_dataset()
    input_buffers = []
    output_buffers = []

    try:
        size = arr.nbytes
        buf, ret = acl.rt.malloc(size, 0)
        assert ret == 0
        ret = acl.rt.memcpy(buf, size, arr.ctypes.data, size, 0)
        assert ret == 0
        acl.mdl.add_dataset_buffer(input_dataset, acl.create_data_buffer(buf, size))
        input_buffers.append((buf, size))

        num_outputs = acl.mdl.get_num_outputs(_model_desc)
        for i in range(num_outputs):
            out_size = acl.mdl.get_output_size_by_index(_model_desc, i)
            buf, ret = acl.rt.malloc(out_size, 0)
            assert ret == 0
            acl.mdl.add_dataset_buffer(output_dataset, acl.create_data_buffer(buf, out_size))
            output_buffers.append((buf, out_size))

        ret = acl.mdl.execute(_model_id, input_dataset, output_dataset)
        assert ret == 0, f"execute failed: {ret}"

        # YOLOv8 has a single output
        buf, out_size = output_buffers[0]
        dims, ret = acl.mdl.get_output_dims(_model_desc, 0)
        assert ret == 0
        out = np.zeros(out_size // 4, dtype=np.float32)
        ret = acl.rt.memcpy(out.ctypes.data, out_size, buf, out_size, 0)
        assert ret == 0
        return out.reshape(dims["dims"])

    finally:
        for buf, _ in input_buffers:
            acl.rt.free(buf)
        for buf, _ in output_buffers:
            acl.rt.free(buf)
        acl.mdl.destroy_dataset(input_dataset)
        acl.mdl.destroy_dataset(output_dataset)


def decode_yolov8(output: np.ndarray, orig_w: int, orig_h: int,
                  conf_thresh: float = 0.25, iou_thresh: float = 0.45) -> list[dict]:
    """
    Decode YOLOv8 output tensor (1, 4+num_classes, 8400) to detections.
    """
    pred = output[0]  # (4+nc, 8400)
    boxes_xywh = pred[:4].T   # (8400, 4) cx,cy,w,h normalized to input size
    scores = pred[4:].T        # (8400, nc)

    class_ids = np.argmax(scores, axis=1)
    confidences = scores[np.arange(len(scores)), class_ids]

    mask = confidences >= conf_thresh
    boxes_xywh = boxes_xywh[mask]
    confidences = confidences[mask]
    class_ids = class_ids[mask]

    if len(boxes_xywh) == 0:
        return []

    # Convert cx,cy,w,h -> x1,y1,x2,y2 (in input image coords)
    _, _, ih, iw = _input_shape
    x1 = (boxes_xywh[:, 0] - boxes_xywh[:, 2] / 2)
    y1 = (boxes_xywh[:, 1] - boxes_xywh[:, 3] / 2)
    x2 = (boxes_xywh[:, 0] + boxes_xywh[:, 2] / 2)
    y2 = (boxes_xywh[:, 1] + boxes_xywh[:, 3] / 2)
    boxes = np.stack([x1, y1, x2, y2], axis=1)

    # NMS per class
    keep = _nms(boxes, confidences, iou_thresh)
    boxes = boxes[keep]
    confidences = confidences[keep]
    class_ids = class_ids[keep]

    # Scale back to original image size
    scale_x, scale_y = orig_w / iw, orig_h / ih
    results = []
    for box, conf, cls_id in zip(boxes, confidences, class_ids):
        x1, y1, x2, y2 = box
        label = _classes[cls_id] if cls_id < len(_classes) else str(cls_id)
        results.append({
            "label": label,
            "class_id": int(cls_id),
            "confidence": round(float(conf), 4),
            "box": {
                "x1": round(float(x1 * scale_x), 1),
                "y1": round(float(y1 * scale_y), 1),
                "x2": round(float(x2 * scale_x), 1),
                "y2": round(float(y2 * scale_y), 1),
            },
        })
    return results


def _nms(boxes: np.ndarray, scores: np.ndarray, iou_thresh: float) -> np.ndarray:
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        ix1 = np.maximum(x1[i], x1[order[1:]])
        iy1 = np.maximum(y1[i], y1[order[1:]])
        ix2 = np.minimum(x2[i], x2[order[1:]])
        iy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, ix2 - ix1) * np.maximum(0, iy2 - iy1)
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[1:][iou <= iou_thresh]
    return np.array(keep)


@app.post("/infer")
async def infer(
    image: UploadFile = File(...),
    conf: float = 0.25,
    iou: float = 0.45,
):
    data = await image.read()
    arr, orig_w, orig_h = preprocess(data)
    output = run_inference(arr)
    detections = decode_yolov8(output, orig_w, orig_h, conf, iou)
    return JSONResponse({"detections": detections, "count": len(detections)})


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model_id is not None}
