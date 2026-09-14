"""
Redaction shim in front of the TencentDB Agent Memory proxy.

    claude / codex  ->  this shim (127.0.0.1:8095)  ->  tdai-proxy (:8096)  ->  upstream LLM
                         redacts request bodies           writes L0 to memory-core

Why this exists: install-memory.ps1 refused claude-mem because its capture reads transcripts
from disk, so there is no point where a redactor can run. The Tencent stack is different - it
captures from the HTTP request path. Anything that sits earlier in that path sees every byte
before memory-core does. This is that point.

What it does, and nothing more:
  - Applies scripts/secret-patterns.txt (the same file the commit gate uses) to request BODIES.
  - Leaves headers alone: the Authorization header carries the sk-mem user key the proxy needs.
  - Streams responses through unbuffered, so SSE token streaming still works.
  - Logs pattern ids and counts only - never the matched text.
  - Refuses to bind anything but loopback.

The honest gap: a secret that matches no pattern passes through. The patterns are regression
tested (test-preflight.ps1, test_memory_redact_shim.py), but they are a list, not a proof.

Stdlib only. Python 3.9+.
"""

from __future__ import annotations

import argparse
import http.client
import ipaddress
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PATTERN_FILE = Path(__file__).with_name("secret-patterns.txt")

# Hop-by-hop headers (RFC 7230 6.1) plus the ones we recompute.
HOP = {"connection", "keep-alive", "proxy-authenticate", "proxy-authorization", "te",
       "trailers", "transfer-encoding", "upgrade", "content-length", "host"}


def load_patterns(path: Path = PATTERN_FILE) -> list[tuple[str, re.Pattern]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 3:
            out.append((parts[0], re.compile(parts[1])))
    if not out:
        raise SystemExit(f"no patterns loaded from {path} - refusing to run an empty guard")
    return out


def redact(body: bytes, patterns) -> tuple[bytes, dict[str, int]]:
    """Replace every pattern hit with [REDACTED:<id>]. The marker is JSON-safe."""
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        return body, {}  # binary payload: nothing a text pattern could match honestly
    hits: dict[str, int] = {}
    for pid, rx in patterns:
        text, n = rx.subn(f"[REDACTED:{pid}]", text)
        if n:
            hits[pid] = hits.get(pid, 0) + n
    return text.encode("utf-8"), hits


def make_handler(target: str, patterns, log=sys.stderr):
    t = urlsplit(target)
    conn_cls = http.client.HTTPSConnection if t.scheme == "https" else http.client.HTTPConnection
    base_path = t.path.rstrip("/")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):  # keep request lines out of logs; paths are fine
            log.write("shim " + (fmt % args) + "\n")

        def _forward(self):
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            body, hits = redact(body, patterns)
            if hits:
                log.write("shim redacted " + ", ".join(f"{k}x{v}" for k, v in sorted(hits.items())) + "\n")

            headers = {k: v for k, v in self.headers.items() if k.lower() not in HOP}
            headers["Content-Length"] = str(len(body))

            upstream = conn_cls(t.hostname, t.port, timeout=600)
            try:
                upstream.request(self.command, base_path + self.path, body=body or None, headers=headers)
                resp = upstream.getresponse()
            except OSError as e:
                self.send_error(502, f"memory proxy unreachable at {target}: {e.__class__.__name__}")
                return

            self.send_response(resp.status, resp.reason)
            for k, v in resp.getheaders():
                if k.lower() not in HOP:
                    self.send_header(k, v)
            self.send_header("Transfer-Encoding", "chunked")
            self.end_headers()
            try:
                while True:
                    chunk = resp.read1(65536)
                    if not chunk:
                        break
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(chunk), chunk))
                    self.wfile.flush()
                self.wfile.write(b"0\r\n\r\n")
            except (BrokenPipeError, ConnectionResetError):
                pass  # client went away mid-stream; nothing to salvage
            finally:
                upstream.close()

        do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _forward

    return Handler


def serve(host: str, port: int, target: str, patterns=None) -> ThreadingHTTPServer:
    if not ipaddress.ip_address(host).is_loopback:
        raise SystemExit(f"refusing to bind {host}: the shim sees raw prompts, loopback only")
    srv = ThreadingHTTPServer((host, port), make_handler(target, patterns or load_patterns()))
    srv.daemon_threads = True
    return srv


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8095)
    ap.add_argument("--target", default="http://127.0.0.1:8096")
    a = ap.parse_args(argv)
    patterns = load_patterns()
    srv = serve(a.host, a.port, a.target, patterns)
    print(f"shim listening on {a.host}:{a.port} -> {a.target} ({len(patterns)} patterns)", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
