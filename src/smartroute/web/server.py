"""Serve the built React studio and its loopback-only simulation API.

Run: python -m smartroute.web.server --port 8765
"""

import argparse
import json
import re
import threading
import time
import uuid
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from smartroute.engine.errors import SmartRouteError
from smartroute.web.live import LiveSession

ROOT = Path(__file__).resolve().parents[3]
MAX_BODY = 512_000


class StudioServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, directory):
        super().__init__(address, partial(StudioHandler, directory=str(directory)))
        self.sessions = {}
        self.sessions_lock = threading.Lock()


class StudioHandler(SimpleHTTPRequestHandler):
    server: StudioServer

    def _json(self, status, value):
        data = json.dumps(value, allow_nan=False, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _body(self):
        if not self.headers.get("Content-Type", "").startswith("application/json"):
            raise ValueError("Expected application/json")
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= MAX_BODY:
            raise ValueError("Invalid or oversized request body")
        # Same-origin local application. Reject cross-site browser writes.
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Cross-site requests are not allowed")
        return json.loads(self.rfile.read(size))

    def _session(self, session_id):
        with self.server.sessions_lock:
            item = self.server.sessions.get(session_id)
            if not item:
                raise KeyError("Live session expired or unavailable. Reset and start again.")
            item["touched"] = time.monotonic()
            return item

    def do_POST(self):
        try:
            body = self._body()
            if self.path == "/api/sessions":
                session = LiveSession(body)
                session_id = uuid.uuid4().hex
                with self.server.sessions_lock:
                    now = time.monotonic()
                    for key in list(self.server.sessions):
                        if now - self.server.sessions[key]["touched"] > 900:
                            del self.server.sessions[key]
                    if len(self.server.sessions) >= 8:
                        raise ValueError(
                            "Session limit reached. Reset an existing studio session first."
                        )
                    self.server.sessions[session_id] = {
                        "session": session,
                        "lock": threading.Lock(),
                        "touched": now,
                    }
                return self._json(201, {"session_id": session_id, **session.payload()})
            match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/step", self.path)
            if match:
                item = self._session(match[1])
                with item["lock"]:
                    return self._json(200, item["session"].step(body))
            self._json(404, {"error": "API endpoint not found"})
        except KeyError as exc:
            self._json(404, {"error": str(exc)})
        except (SmartRouteError, ValueError, TypeError, AttributeError) as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:
            self.log_error("Simulation error: %s", exc)
            self._json(
                500, {"error": "Simulation failed; reset the session and check the server log."}
            )

    def do_DELETE(self):
        match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})", self.path)
        if not match:
            return self._json(404, {"error": "API endpoint not found"})
        origin = self.headers.get("Origin")
        if origin and urlparse(origin).hostname not in ("127.0.0.1", "localhost", "::1"):
            return self._json(403, {"error": "Cross-site requests are not allowed"})
        with self.server.sessions_lock:
            self.server.sessions.pop(match[1], None)
        self._json(200, {"deleted": True})

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/health":
            return self._json(
                200, {"status": "ok", "engine": "SimPy + SmartRoute", "interval_s": 0.2}
            )
        match = re.fullmatch(r"/api/sessions/([a-f0-9]{32})/export", path)
        if match:
            try:
                item = self._session(match[1])
                with item["lock"]:
                    return self._json(200, item["session"].export())
            except KeyError as exc:
                return self._json(404, {"error": str(exc)})
        if path.startswith("/api/"):
            return self._json(404, {"error": "API endpoint not found"})
        if path in ("/", "/index.html") and not (Path(self.directory) / "index.html").exists():
            return self._json(
                503, {"error": "Frontend is not built. Run npm ci && npm run build in frontend/."}
            )
        return super().do_GET()

    def list_directory(self, path):
        self.send_error(404)


def main():
    parser = argparse.ArgumentParser(description="SmartRoute React network studio")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = StudioServer(("127.0.0.1", args.port), ROOT / "frontend" / "dist")
    print(f"SmartRoute Network Studio: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
