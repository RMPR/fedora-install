"""Publishing to several platforms at once, shared by the GUI and the CLI."""

import datetime as dt
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from . import config
from .http import HTTPError
from .platforms import PLATFORMS


@dataclass
class Result:
    platform: str
    url: str = ""
    error: str = ""

    @property
    def ok(self):
        return not self.error


class CachedSecrets:
    """Read each keyring entry at most once per publish."""

    def __init__(self, store):
        self.store, self.cache = store, {}

    def get(self, name):
        if name not in self.cache:
            self.cache[name] = self.store.get(name)
        return self.cache[name]


def problems(text, targets, cfg, secrets):
    """Reasons the post can't go out yet, keyed by platform. Empty means ready."""
    out = {}
    if not text.strip():
        return {"*": ["nothing to post"]}
    for name in targets:
        p = PLATFORMS[name]
        issues = list(p.missing(cfg, secrets))
        if p.LIMIT and p.length(text) > p.LIMIT:
            issues.append(f"{p.length(text) - p.LIMIT} characters over the limit")
        if issues:
            out[name] = issues
    return out


def _describe(exc):
    if isinstance(exc, HTTPError):
        try:
            body = json.loads(exc.body)
            msg = body.get("detail") or body.get("message") or body.get("title") or exc.body
        except ValueError:
            msg = exc.body
        return f"HTTP {exc.status}: {str(msg)[:300]}"
    return str(exc) or type(exc).__name__


def publish(text, targets, cfg, secrets, platforms=PLATFORMS):
    """Post `text` to every target concurrently. Never raises; one failing
    platform doesn't stop the others."""

    def one(name):
        try:
            return Result(name, url=platforms[name].post(text, cfg, secrets))
        except Exception as exc:  # noqa: BLE001 - reported to the user
            return Result(name, error=_describe(exc))

    with ThreadPoolExecutor(max_workers=max(1, len(targets))) as pool:
        results = list(pool.map(one, targets))
    log(text, results)
    return results


def log(text, results):
    """Append to a local, private record of what was posted (and where)."""
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with (config.DATA_DIR / "history.jsonl").open("a") as f:
            f.write(json.dumps({
                "at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
                "text": text,
                "results": {r.platform: r.url or ("error: " + r.error) for r in results},
            }, ensure_ascii=False) + "\n")
    except OSError:
        pass
