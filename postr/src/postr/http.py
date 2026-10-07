"""Tiny stdlib HTTP helper so postr has no third-party dependencies."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field


class HTTPError(Exception):
    def __init__(self, status, body, url):
        self.status = status
        self.body = body
        self.url = url
        super().__init__(f"HTTP {status} from {url}: {body[:500]}")


@dataclass
class Response:
    status: int
    body: str
    headers: dict = field(default_factory=dict)

    def json(self):
        return json.loads(self.body) if self.body else {}


def request(method, url, *, headers=None, json_body=None, data=None, timeout=30):
    headers = dict(headers or {})
    payload = None
    if json_body is not None:
        payload = json.dumps(json_body).encode()
        headers.setdefault("Content-Type", "application/json")
    elif data is not None:
        payload = data if isinstance(data, bytes) else data.encode()
    headers.setdefault("User-Agent", "postr")
    req = urllib.request.Request(url, data=payload, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return Response(
                resp.status,
                resp.read().decode("utf-8", "replace"),
                {k.lower(): v for k, v in resp.headers.items()},
            )
    except urllib.error.HTTPError as e:
        raise HTTPError(e.code, e.read().decode("utf-8", "replace"), url) from None
