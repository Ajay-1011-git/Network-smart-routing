import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from smartroute.web.server import StudioServer


@pytest.fixture(scope="module")
def endpoint(tmp_path_factory):
    root = tmp_path_factory.mktemp("studio-public")
    (root / "index.html").write_text("<!doctype html><title>Static serving test fixture</title>")
    server = StudioServer(("127.0.0.1", 0), root)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def request(endpoint, path, data=None, method=None, origin=None):
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    request = Request(
        endpoint + path,
        data=json.dumps(data).encode() if data is not None else None,
        method=method,
        headers=headers,
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def network():
    return {
        "nodes": [
            {"id": id_, "kind": "router", "label": id_, "position": {"x": 0, "y": 0}}
            for id_ in ("a", "b")
        ],
        "connections": [
            {"id": "c", "source": "a", "target": "b", "capacity_mbps": 1.0, "latency_ms": 2}
        ],
        "flows": [{"id": "f", "source": "a", "target": "b", "rate_mbps": 0.5}],
    }


def test_real_api_session_step_export_delete(endpoint):
    status, health = request(endpoint, "/api/health")
    assert status == 200 and health["engine"] == "SimPy + SmartRoute"
    status, created = request(endpoint, "/api/sessions", network())
    assert status == 201
    id_ = created["session_id"]
    for _ in range(3):
        status, state = request(endpoint, f"/api/sessions/{id_}/step", {})
        assert status == 200
    assert state["time_s"] == 0.6 and state["metrics"]["generated"] > 0
    status, exported = request(endpoint, f"/api/sessions/{id_}/export")
    assert (
        status == 200
        and exported["packets"]
        and exported["kind"] == "smartroute-interactive-session"
    )
    assert request(endpoint, f"/api/sessions/{id_}", method="DELETE")[0] == 200
    assert request(endpoint, f"/api/sessions/{id_}/step", {})[0] == 404


def test_bad_networks_and_cross_site_requests_fail_visibly(endpoint):
    invalid = network()
    invalid["connections"][0]["capacity_mbps"] = 0
    status, data = request(endpoint, "/api/sessions", invalid)
    assert status == 400 and "capacity" in data["error"].lower()
    assert (
        request(endpoint, "/api/sessions", network(), origin="https://untrusted.example")[0] == 400
    )
    assert request(endpoint, "/api/missing")[0] == 404


def test_static_shell_is_served_without_directory_listing(endpoint):
    with urlopen(endpoint + "/", timeout=5) as response:
        assert response.status == 200
        assert b"Static serving test fixture" in response.read()
