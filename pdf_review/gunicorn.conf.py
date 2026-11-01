"""One process owns all Socket.IO room and presence state."""

import ipaddress
import os

host = os.environ.get("PDF_REVIEW_HOST", "127.0.0.1")
if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
    raise RuntimeError("PDF Review must bind to a loopback host.")
port = int(os.environ.get("PDF_REVIEW_PORT", "8002"))
if not 1 <= port <= 65535:
    raise RuntimeError("PDF_REVIEW_PORT must be between 1 and 65535.")
bind = f"[{host}]:{port}" if ":" in host else f"{host}:{port}"
workers = 1
worker_class = "gthread"
threads = 100
accesslog = None
errorlog = "-"


def on_starting(server):
    if server.cfg.workers != 1:
        raise RuntimeError("PDF Review requires exactly one Gunicorn worker process.")
    if server.cfg.worker_class_str != "gthread" or server.cfg.threads < 2:
        raise RuntimeError("PDF Review requires the multithreaded gthread worker.")
