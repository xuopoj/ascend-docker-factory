"""
Generic Ascend OM model server.
Loads any .om file and exposes it via HTTP.

Usage:
    MODEL_PATH=/models/yolov8n.om uvicorn serve:app --host 0.0.0.0 --port 8000

POST /infer
  - image upload (multipart or raw image bytes): server preprocesses to model input shape
  - raw tensor (application/octet-stream): float32 bytes passed directly, X-Input-Shape header required

GET /health
"""
import io
import os
from contextlib import asynccontextmanager

import numpy as np
from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import Response

import acl


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_acl()
    yield
    shutdown()


app = FastAPI(lifespan=lifespan)

_context = None
_model_id = None
_model_desc = None

# Input shape for image preprocessing, e.g. "1,3,640,640"
_input_shape = None


def init_acl():
    global _context, _model_id, _model_desc, _input_shape

    model_path = os.environ.get("MODEL_PATH")
    if not model_path:
        raise RuntimeError("MODEL_PATH environment variable not set")

    device_id = int(os.environ.get("DEVICE_ID", "0"))

    shape_str = os.environ.get("INPUT_SHAPE")
    if shape_str:
        _input_shape = tuple(int(x) for x in shape_str.split(","))

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


def preprocess_image(data: bytes) -> np.ndarray:
    """Decode image bytes and convert to float32 BCHW tensor."""
    from PIL import Image
    if _input_shape is None:
        raise HTTPException(400, "INPUT_SHAPE env var required for image input (e.g. '1,3,640,640')")
    _, _, h, w = _input_shape
    img = Image.open(io.BytesIO(data)).convert("RGB").resize((w, h))
    arr = np.array(img, dtype=np.float32) / 255.0   # HWC, [0,1]
    arr = arr.transpose(2, 0, 1)[np.newaxis, ...]    # -> BCHW
    return arr


def run_inference(inputs: list[np.ndarray]) -> list[np.ndarray]:
    input_dataset = acl.mdl.create_dataset()
    output_dataset = acl.mdl.create_dataset()
    input_buffers = []
    output_buffers = []

    try:
        num_inputs = acl.mdl.get_num_inputs(_model_desc)
        if len(inputs) != num_inputs:
            raise HTTPException(400, f"Model expects {num_inputs} inputs, got {len(inputs)}")

        for arr in inputs:
            arr = np.ascontiguousarray(arr, dtype=np.float32)
            size = arr.nbytes
            buf, ret = acl.rt.malloc(size, 0)
            assert ret == 0, f"malloc failed: {ret}"
            ret = acl.rt.memcpy(buf, size, arr.ctypes.data, size, 0)
            assert ret == 0, f"memcpy H2D failed: {ret}"
            acl.mdl.add_dataset_buffer(input_dataset, acl.create_data_buffer(buf, size))
            input_buffers.append((buf, size))

        num_outputs = acl.mdl.get_num_outputs(_model_desc)
        for i in range(num_outputs):
            size = acl.mdl.get_output_size_by_index(_model_desc, i)
            buf, ret = acl.rt.malloc(size, 0)
            assert ret == 0, f"malloc failed: {ret}"
            acl.mdl.add_dataset_buffer(output_dataset, acl.create_data_buffer(buf, size))
            output_buffers.append((buf, size))

        ret = acl.mdl.execute(_model_id, input_dataset, output_dataset)
        if ret != 0:
            raise HTTPException(500, f"Inference failed: {ret}")

        outputs = []
        for i, (buf, size) in enumerate(output_buffers):
            dims, ret = acl.mdl.get_output_dims(_model_desc, i)
            assert ret == 0
            dtype_id = acl.mdl.get_output_data_type(_model_desc, i)
            # dtype_id: 0=float32, 1=float16, 2=int8, 3=int32
            dtype = {0: np.float32, 1: np.float16, 2: np.int8, 3: np.int32}.get(dtype_id, np.float32)
            out = np.zeros(size // np.dtype(dtype).itemsize, dtype=dtype)
            ret = acl.rt.memcpy(out.ctypes.data, size, buf, size, 0)
            assert ret == 0, f"memcpy D2H failed: {ret}"
            outputs.append(out.reshape(dims["dims"]))

    finally:
        for buf, _ in input_buffers:
            acl.rt.free(buf)
        for buf, _ in output_buffers:
            acl.rt.free(buf)
        acl.mdl.destroy_dataset(input_dataset)
        acl.mdl.destroy_dataset(output_dataset)

    return outputs


@app.post("/infer")
async def infer(request: Request, image: UploadFile = File(default=None)):
    content_type = request.headers.get("content-type", "")

    if image is not None or content_type.startswith("multipart/"):
        # Image upload — preprocess on server
        data = await image.read()
        arr = preprocess_image(data)
        inputs = [arr]

    elif content_type.startswith("image/"):
        # Raw image bytes
        data = await request.body()
        arr = preprocess_image(data)
        inputs = [arr]

    elif content_type == "application/octet-stream":
        # Raw float32 tensor bytes — shape must be provided via header
        shape_header = request.headers.get("x-input-shape")
        if not shape_header:
            raise HTTPException(400, "x-input-shape header required for octet-stream (e.g. '1,3,640,640')")
        shape = tuple(int(x) for x in shape_header.split(","))
        data = await request.body()
        arr = np.frombuffer(data, dtype=np.float32).reshape(shape)
        inputs = [arr]

    else:
        raise HTTPException(415, "Unsupported content type. Use multipart/form-data, image/*, or application/octet-stream")

    outputs = run_inference(inputs)

    # Return raw bytes of all outputs, with shape info in headers
    # Each output is concatenated; use x-output-shapes to parse
    shapes = ",".join("|".join(str(d) for d in o.shape) for o in outputs)
    body = b"".join(o.astype(np.float32).tobytes() for o in outputs)
    return Response(
        content=body,
        media_type="application/octet-stream",
        headers={"x-output-shapes": shapes},
    )


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model_id is not None}
