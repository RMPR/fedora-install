"""Mastodon via the official REST API (POST /api/v1/statuses).

On your instance: Preferences → Development → New application, scope
`write:statuses` only, then copy "Your access token".
"""

import re
import uuid

from .. import http

NAME = "mastodon"
LABEL = "Mastodon"
LIMIT = 500  # Mastodon's default; override with [mastodon] max_characters

_URL = re.compile(r"https?://\S+", re.IGNORECASE)
# @user@domain counts only as @user.
_MENTION = re.compile(r"(?<![\w@])(@\w+)@[\w.-]+\w")


def length(text):
    text = _MENTION.sub(r"\1", text)
    return len(_URL.sub("x" * 23, text))


def limit(cfg):
    return int(cfg["mastodon"].get("max_characters") or LIMIT)


def missing(cfg, secrets):
    out = []
    if not cfg["mastodon"].get("instance"):
        out.append("mastodon instance")
    if not secrets.get("mastodon_access_token"):
        out.append("mastodon_access_token")
    return out


def post(text, cfg, secrets):
    instance = cfg["mastodon"]["instance"].rstrip("/")
    if "://" not in instance:
        instance = "https://" + instance
    resp = http.request(
        "POST", f"{instance}/api/v1/statuses",
        headers={
            "Authorization": "Bearer " + secrets.get("mastodon_access_token"),
            # Makes a retried request return the first post instead of a duplicate.
            "Idempotency-Key": str(uuid.uuid4()),
        },
        json_body={"status": text, "visibility": cfg["mastodon"].get("visibility", "public")},
    )
    return resp.json()["url"]
