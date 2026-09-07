from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import ssl
import threading
import time
import queue
from dataclasses import dataclass
from urllib.parse import quote, unquote, urljoin, urlsplit

from qa_engine.domain import Project


class PolicyBlocked(ValueError):
    pass


class BudgetExceeded(RuntimeError):
    pass


class Redactor:
    def __init__(self, secrets=()):
        variants = set()
        for value in secrets:
            if value:
                variants.update((value, quote(value, safe=""), json.dumps(value)[1:-1]))
        self.secrets = sorted(variants, key=len, reverse=True)

    def text(self, text: str) -> str:
        for value in self.secrets:
            text = text.replace(value, "[REDACTED]")
        text = re.sub(r"(?i)(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
        text = re.sub(r"(?i)(https?://[^\s?#\"<>]+)\?[^\s\"<>]*", r"\1?[REDACTED]", text)
        text = re.sub(r"(?i)(bearer|basic)\s+[a-z0-9+/_.=:-]+", r"\1 [REDACTED]", text)
        text = re.sub(
            r"(?i)((?:password|passwd|secret|token|api[_-]?key|authorization|cookie|set-cookie)\s*[\"']?\s*[:=]\s*)[^\r\n,;]+",
            r"\1[REDACTED]",
            text,
        )
        text = re.sub(r"-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----", "[REDACTED]", text)
        return text

    def clean(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            if (
                str(value.get("name", "")).lower() in {"cookie", "set-cookie", "authorization", "proxy-authorization", "x-api-key"}
                and "value" in value
            ):
                return {**value, "value": "[REDACTED]"}
            return {
                self.text(str(k)): "[REDACTED]"
                if re.search(r"(?i)^(password|secret|token|api[_-]?key|authorization|cookie|set-cookie)$", str(k))
                else self.clean(v)
                for k, v in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.clean(x) for x in value]
        return value


class SecretProvider:
    """Only explicitly bound environment variables; no cross-project lookup fallback."""

    def __init__(self, project: Project):
        self.project = project

    def resolve(self, ref: str) -> str:
        if ref not in self.project.credentials:
            raise PolicyBlocked("CREDENTIAL_NOT_BOUND")
        value = os.environ.get(self.project.credentials[ref])
        if not value:
            raise PolicyBlocked("CREDENTIAL_UNAVAILABLE")
        return value

    def available(self) -> dict[str, str]:
        return {ref: os.environ[var] for ref, var in self.project.credentials.items() if os.environ.get(var)}


def digest(value) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(data).hexdigest()


def fingerprint(check_id: str, executor: str, code: str, text: str, redactor: Redactor) -> str:
    text = redactor.text(text).lower()
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", "<uuid>", text)
    text = re.sub(r"\d{4}-\d\d-\d\d[t ][\d:.+z-]+", "<time>", text)
    text = re.sub(r"(?<=:)\d{2,5}\b", "<port>", text)
    text = re.sub(r"\b(?:request[_-]?id|random[_-]?id)\s*[:=]\s*\S+", "<id>", text)
    return "v1:" + digest([check_id, executor, code, " ".join(text.split())])


class URLGuard:
    def __init__(self, project: Project):
        self.project = project

    def parse(self, url: str):
        if any(ord(c) < 33 or ord(c) == 127 for c in url) or "\\" in url:
            raise PolicyBlocked("INVALID_URL")
        try:
            p = urlsplit(url)
            host = p.hostname or ""
            port = p.port or (443 if p.scheme == "https" else 80)
        except ValueError as exc:
            raise PolicyBlocked("INVALID_URL") from exc
        if p.scheme not in {"http", "https"} or not host or p.username or p.password or p.fragment:
            raise PolicyBlocked("INVALID_URL")
        if "%" in host or host.endswith("."):
            raise PolicyBlocked("INVALID_HOST")
        try:
            host = host.encode("idna").decode("ascii").lower()
        except UnicodeError as exc:
            raise PolicyBlocked("INVALID_HOST") from exc
        if host not in self.project.policy.allowed_hosts or port not in self.project.policy.allowed_ports:
            raise PolicyBlocked("TARGET_NOT_AUTHORIZED")
        if re.search(r"(?i)(token|password|secret|api[_-]?key|signature)=", unquote(p.query)):
            raise PolicyBlocked("SECRET_BEARING_URL")
        return p, host, port

    def resolve(self, url: str):
        p, host, port = self.parse(url)
        answers = queue.Queue(maxsize=1)

        def resolve_dns():
            try:
                answers.put(socket.getaddrinfo(host, port, type=socket.SOCK_STREAM))
            except OSError as exc:
                answers.put(exc)

        threading.Thread(target=resolve_dns, daemon=True).start()
        try:
            result = answers.get(timeout=min(5, self.project.policy.timeout_seconds))
        except queue.Empty:
            raise TimeoutError("DNS_DEADLINE_EXCEEDED") from None
        if isinstance(result, OSError):
            raise OSError("DNS_RESOLUTION_FAILED") from None
        addresses = {info[4][0] for info in result}
        if not addresses:
            raise PolicyBlocked("NO_TARGET_ADDRESS")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            local = ip.is_loopback and self.project.environment == "local" and self.project.policy.allow_loopback
            if (not ip.is_global and not local) or ip.is_multicast or getattr(ip, "ipv4_mapped", None):
                raise PolicyBlocked("FORBIDDEN_ADDRESS")
        return p, host, port, sorted(addresses)[0]


@dataclass
class HTTPResponse:
    status: int
    headers: dict[str, str]
    body: bytes
    duration_ms: int
    url: str


class SafeHTTP:
    """Pinned connect address with original Host/TLS identity; no proxy environment or auto redirects."""

    def __init__(self, project: Project):
        self.project = project
        self.guard = URLGuard(project)
        self.requests = 0
        self.lock = threading.Lock()

    def request(self, url, method="GET", headers=None, body=None, *, follow=True):
        allowed = {"GET", "HEAD", "OPTIONS"}
        if self.project.policy.allow_mutation:
            allowed.add("POST")
        if method not in allowed:
            raise PolicyBlocked("HTTP_METHOD_NOT_AUTHORIZED")
        started = time.monotonic()
        headers = dict(headers or {})
        for redirect in range(6):
            with self.lock:
                self.requests += 1
                if self.requests > self.project.policy.max_requests:
                    raise BudgetExceeded("REQUEST_BUDGET_EXCEEDED")
            p, host, port, address = self.guard.resolve(url)
            timeout = self.project.policy.timeout_seconds - (time.monotonic() - started)
            if timeout <= 0:
                raise TimeoutError("HTTP_DEADLINE_EXCEEDED")
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
            sock = socket.create_connection((address, port), timeout=timeout)
            try:
                if p.scheme == "https":
                    sock = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
                conn.sock = sock
                clean_headers = {
                    k: v
                    for k, v in headers.items()
                    if k.lower() not in {"host", "connection", "proxy-authorization", "content-length", "accept-encoding"}
                }
                clean_headers["Accept-Encoding"] = "identity"
                conn.request(method, p.path + ("?" + p.query if p.query else "") or "/", body=body, headers=clean_headers)
                # Keep ownership of the pinned socket until bounded body reading finishes.
                # HTTPConnection.getresponse() closes its socket for HTTP/1.0 responses.
                response = http.client.HTTPResponse(sock, method=method)
                response.begin()
                chunks = bytearray()
                while True:
                    remaining = self.project.policy.timeout_seconds - (time.monotonic() - started)
                    if remaining <= 0:
                        raise TimeoutError("HTTP_DEADLINE_EXCEEDED")
                    sock.settimeout(remaining)
                    part = response.read1(min(65536, self.project.policy.max_response_bytes + 1 - len(chunks)))
                    chunks.extend(part)
                    if len(chunks) > self.project.policy.max_response_bytes:
                        raise BudgetExceeded("RESPONSE_SIZE_EXCEEDED")
                    if not part:
                        break
                response_headers = {}
                for key, value in response.getheaders():
                    key = key.lower()
                    response_headers[key] = (
                        response_headers[key] + "\n" + value if key == "set-cookie" and key in response_headers else value
                    )
                result = HTTPResponse(response.status, response_headers, bytes(chunks), int((time.monotonic() - started) * 1000), url)
                response.close()
            finally:
                conn.close()
                sock.close()
            if result.status in {301, 302, 303, 307, 308} and "location" in result.headers:
                dest = urljoin(url, result.headers["location"])
                self.guard.resolve(dest)
                if not follow:
                    return result
                if urlsplit(dest).netloc != urlsplit(url).netloc:
                    headers = {k: v for k, v in headers.items() if k.lower() not in {"authorization", "cookie"}}
                if result.status == 303 or (result.status in {301, 302} and method == "POST"):
                    method, body = "GET", None
                url = dest
            else:
                return result
        raise PolicyBlocked("REDIRECT_LIMIT_EXCEEDED")
