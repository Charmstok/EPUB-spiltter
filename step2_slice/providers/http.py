from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


class HttpError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, body: bytes | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


def post_json(
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout_s: float,
) -> HttpResponse:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read()
            return HttpResponse(
                status=int(getattr(resp, "status", 200)),
                headers={k.lower(): v for k, v in resp.headers.items()},
                body=body,
            )
    except urllib.error.HTTPError as e:
        body = e.read() if hasattr(e, "read") else b""
        raise HttpError(f"HTTP {e.code} for {url}", status=int(e.code), body=body) from e
    except (urllib.error.URLError, socket.timeout) as e:
        raise HttpError(f"Network error for {url}: {e}") from e

