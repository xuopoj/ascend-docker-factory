"""Disable TLS verification for aiohttp so ais_bench can hit self-signed HTTPS
endpoints. Auto-imported via PYTHONPATH; only active when AIS_INSECURE_SSL=1."""
import os

if os.environ.get("AIS_INSECURE_SSL") == "1":
    import ssl
    import aiohttp

    _ctx = ssl.create_default_context()
    _ctx.check_hostname = False
    _ctx.verify_mode = ssl.CERT_NONE

    _orig_conn_init = aiohttp.TCPConnector.__init__

    def _patched_conn_init(self, *args, **kwargs):
        kwargs.setdefault("ssl", _ctx)
        _orig_conn_init(self, *args, **kwargs)

    aiohttp.TCPConnector.__init__ = _patched_conn_init

    _orig_sess_init = aiohttp.ClientSession.__init__

    def _patched_sess_init(self, *args, **kwargs):
        if kwargs.get("connector") is None and len(args) == 0:
            kwargs["connector"] = aiohttp.TCPConnector(ssl=_ctx)
        _orig_sess_init(self, *args, **kwargs)

    aiohttp.ClientSession.__init__ = _patched_sess_init
    print("[sitecustomize] aiohttp TLS verification disabled (AIS_INSECURE_SSL=1)")

# Endpoint-path override: VLLMCustomAPIChat hardcodes "v1/chat/completions".
# Set AIS_FULL_URL to post to a different path verbatim (e.g. .../api/v2/chat/completions).
_full_url = os.environ.get("AIS_FULL_URL")
if _full_url:
    from ais_bench.benchmark.models.api_models.vllm_custom_api_chat import VLLMCustomAPIChat

    def _override_get_url(self):
        return _full_url

    VLLMCustomAPIChat._get_url = _override_get_url
    print(f"[sitecustomize] chat endpoint overridden -> {_full_url}")
