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
