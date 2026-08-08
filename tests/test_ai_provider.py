"""
Smoke test for services.ai_provider.CloudAIProvider (#87).

Spins up a real local HTTP server implementing the provider contract
(docs/AI_ARCHITECTURE.md's "Future-Proofing" section) so this is an
actual round trip, not a mocked one -- proves CloudAIProvider is
genuinely functional against anything speaking the contract, not just
a decorative class. Also checks the failure path (nothing listening)
returns AIResponse(ok=False, ...) rather than raising, per
AIProvider's contract.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from services.ai_provider import CloudAIProvider


class _StubHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        request = json.loads(self.rfile.read(length))

        if request["task"] == "suggest_concepts":
            body = {
                "ok": True,
                "data": {"suggestions": [{"category": "field_of_study", "value": "Sociology"}]},
                "confidence": 0.8,
                "error": None,
            }
        else:
            body = {"ok": False, "data": None, "confidence": None, "error": "unsupported task"}

        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass  # keep test output quiet


def _run_stub_server():
    server = HTTPServer(("127.0.0.1", 0), _StubHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main():
    server = _run_stub_server()
    port = server.server_address[1]

    try:
        provider = CloudAIProvider(endpoint_url=f"http://127.0.0.1:{port}")

        response = provider.suggest_concepts("A study of urban policy and robotics.")
        assert response.ok, f"expected ok=True, got error={response.error!r}"
        assert response.data["suggestions"][0]["value"] == "Sociology"
        assert response.confidence == 0.8
        print("PASS: suggest_concepts round trip against a real HTTP server")

        response = provider.detect_disciplines("A study of urban policy and robotics.")
        assert not response.ok
        assert response.error == "unsupported task"
        print("PASS: provider-reported failure surfaces as ok=False, not an exception")

        response = provider.suggest_concepts("")
        assert not response.ok
        print("PASS: empty input rejected before any HTTP call")
    finally:
        server.shutdown()

    unreachable = CloudAIProvider(endpoint_url="http://127.0.0.1:1")  # nothing listens on port 1
    response = unreachable.suggest_concepts("A study of urban policy and robotics.")
    assert not response.ok
    assert response.error
    print(f"PASS: connection failure handled gracefully (error={response.error!r})")

    print("\nAll CloudAIProvider checks passed.")


if __name__ == "__main__":
    main()
