from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from human_review.review_queue import ReviewQueue
from qa_agent.logging_utils import get_logger

logger = get_logger(__name__)


def create_handler(queue: ReviewQueue) -> type[BaseHTTPRequestHandler]:
    class ApprovalHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            parts = parsed.path.strip("/").split("/")
            query = parse_qs(parsed.query)
            if len(parts) != 2 or parts[0] not in {"approve", "reject"}:
                self._send(404, {"error": "Use /approve/<report_id> or /reject/<report_id>"})
                return

            notes = query.get("notes", [""])[0]
            try:
                if parts[0] == "approve":
                    record = queue.approve(parts[1], notes)
                else:
                    record = queue.reject(parts[1], notes)
                self._send(200, record)
            except FileNotFoundError:
                self._send(404, {"error": "Report not found"})

        def log_message(self, format: str, *args: object) -> None:
            logger.info(format, *args)

        def _send(self, status: int, body: dict) -> None:
            payload = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    return ApprovalHandler


def run_server(host: str = "127.0.0.1", port: int = 8088) -> None:
    queue = ReviewQueue()
    server = ThreadingHTTPServer((host, port), create_handler(queue))
    logger.info("Approval API listening on http://%s:%s", host, port)
    server.serve_forever()

