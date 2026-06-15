import json
import time
import random
import string
from http.server import HTTPServer, BaseHTTPRequestHandler

WORDS = "the quick brown fox jumps over the lazy dog and then runs away".split()

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        stream = body.get("stream", False)
        max_tokens = body.get("max_tokens", 64)
        model = body.get("model", "mock-model")
        req_id = f"chatcmpl-{''.join(random.choices(string.ascii_lowercase, k=8))}"

        if stream:
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i in range(max_tokens):
                word = random.choice(WORDS)
                chunk = {
                    "id": req_id, "object": "chat.completion.chunk", "model": model,
                    "choices": [{"index": 0, "delta": {"content": word + " "}, "finish_reason": None}],
                }
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
            done = {
                "id": req_id, "object": "chat.completion.chunk", "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            self.wfile.write(f"data: {json.dumps(done)}\n\ndata: [DONE]\n\n".encode())
        else:
            text = " ".join(random.choice(WORDS) for _ in range(max_tokens))
            resp = {
                "id": req_id, "object": "chat.completion", "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": max_tokens, "total_tokens": 10 + max_tokens},
            }
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())

    def do_GET(self):
        if "/models" in self.path:
            resp = {"data": [{"id": "mock-model", "object": "model"}]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())

    def log_message(self, fmt, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8000), Handler)
    print("Mock LLM server on :8000")
    server.serve_forever()
