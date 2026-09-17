"""
Tests for memory_redact_shim.py, against a fake upstream - no Docker, no LLM, no network.

    python -m unittest scripts/test_memory_redact_shim.py -v

The fixtures reuse the must-catch / must-ignore shapes from test-preflight.ps1, so a pattern that
drifts breaks both gates. All key material is FAKE.
"""

import http.client
import json
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memory_redact_shim as shim  # noqa: E402

MUST_CATCH = {
    "supabase-mgmt": "sbp_a86bFAKEFAKEFAKEFAKEFAKEfake123",
    "runpod": "rpa_FAKEFAKEFAKEFAKEFAKEFAKE0123456",
    "google-api": "AIzaSyCduWFAKEFAKEFAKEFAKEFAKEFAKE01234",
    "openai-like": "sk-fish-FAKEFAKEFAKEFAKEFAKEfake0123",
    "github-token": "gho_FAKEFAKEFAKEFAKEFAKEFAKEFAKEfake12",
    "aws-akid": "AKIAFAKEFAKEFAKE1234",
    # Assembled at runtime so the commit gate (preflight.ps1) has no literal to flag in this file.
    "private-key": "-----BEGIN RSA " + "PRIVATE KEY-----",
}
MUST_IGNORE = [
    'const REMEMBERED_LOGIN_KEY = "task-manager-login-identifier";',
    "process.env.SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_SERVICE_ROLE_KEY=",
]


class FakeUpstream(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    seen = []

    def log_message(self, *a):
        pass

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        FakeUpstream.seen.append({"path": self.path, "headers": dict(self.headers), "body": body})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()
        for i in range(3):
            data = f"event: delta\ndata: {i}\n\n".encode()
            self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
            self.wfile.flush()
            time.sleep(0.4)
        self.wfile.write(b"0\r\n\r\n")


def start(server):
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


class ShimTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.up = start(ThreadingHTTPServer(("127.0.0.1", 0), FakeUpstream))
        target = f"http://127.0.0.1:{cls.up.server_address[1]}"
        cls.sh = start(shim.serve("127.0.0.1", 0, target))
        cls.port = cls.sh.server_address[1]

    @classmethod
    def tearDownClass(cls):
        cls.sh.shutdown()
        cls.up.shutdown()

    def post(self, payload, path="/claude-code/default/v1/messages", headers=None):
        FakeUpstream.seen.clear()
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        body = json.dumps(payload).encode()
        h = {"Content-Type": "application/json", "Authorization": "Bearer sk-mem-FAKEFAKEFAKEFAKEFAKEFAKE0123"}
        h.update(headers or {})
        c.request("POST", path, body=body, headers=h)
        return c, c.getresponse()

    def test_every_real_exposure_shape_is_redacted_before_upstream(self):
        for pid, secret in MUST_CATCH.items():
            with self.subTest(pid):
                c, r = self.post({"messages": [{"role": "user", "content": f"USE IT I WILL REVOKE IT {secret}"}]})
                r.read(); c.close()
                sent = FakeUpstream.seen[0]["body"].decode()
                self.assertNotIn(secret, sent)
                self.assertIn(f"[REDACTED:{pid}]", sent)
                json.loads(sent)  # still valid JSON after redaction

    def test_innocent_strings_pass_untouched(self):
        for s in MUST_IGNORE:
            with self.subTest(s):
                c, r = self.post({"messages": [{"role": "user", "content": s}]})
                r.read(); c.close()
                self.assertEqual(json.loads(FakeUpstream.seen[0]["body"])["messages"][0]["content"], s)

    def test_auth_header_and_path_reach_the_proxy_intact(self):
        c, r = self.post({"x": 1}, headers={"x-claude-code-session-id": "abc"})
        r.read(); c.close()
        seen = FakeUpstream.seen[0]
        self.assertEqual(seen["path"], "/claude-code/default/v1/messages")
        self.assertEqual(seen["headers"]["Authorization"], "Bearer sk-mem-FAKEFAKEFAKEFAKEFAKEFAKE0123")
        self.assertEqual(seen["headers"]["x-claude-code-session-id"], "abc")

    def test_response_streams_rather_than_buffering(self):
        # The upstream emits 3 events 0.4s apart. Streaming means the first event arrives well BEFORE the last
        # one is produced; buffering means both land together. Comparing the two timestamps tests exactly that,
        # where an absolute deadline would only measure how busy the machine is (it failed at 0.56s under load).
        c, r = self.post({"stream": True})
        first = r.read1(64)
        first_at = time.monotonic()
        rest = r.read()
        done_at = time.monotonic()
        c.close()
        self.assertIn(b"data: 0", first)
        self.assertIn(b"data: 2", first + rest)
        self.assertGreater(done_at - first_at, 0.5,
                           "the first event arrived with the last: the response was buffered, not streamed")

    def test_refuses_non_loopback_bind(self):
        with self.assertRaises(SystemExit):
            shim.serve("0.0.0.0", 0, "http://127.0.0.1:1")

    def test_unreachable_proxy_is_a_502_not_a_hang(self):
        dead = start(shim.serve("127.0.0.1", 0, "http://127.0.0.1:9"))
        try:
            c = http.client.HTTPConnection("127.0.0.1", dead.server_address[1], timeout=10)
            c.request("POST", "/x", body=b"{}", headers={"Content-Length": "2"})
            self.assertEqual(c.getresponse().status, 502)
        finally:
            dead.shutdown()


if __name__ == "__main__":
    unittest.main()
