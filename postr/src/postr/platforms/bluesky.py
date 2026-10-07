"""Bluesky via the official AT Protocol XRPC API.

Uses an app password (Settings → Privacy and security → App passwords), never
your main password. Links, #hashtags and @mentions are turned into rich-text
facets so they are clickable, as they would be in the official app.
"""

import datetime as dt
import re
import unicodedata
import urllib.parse

from .. import http

NAME = "bluesky"
LABEL = "Bluesky"
LIMIT = 300  # graphemes

_URL = re.compile(r"https?://[^\s]+", re.IGNORECASE)
_TRAILING = ".,;:!?\"')]"
_HASHTAG = re.compile(r"(?<![\w#&])#(\w*[^\W\d]\w*)")
_MENTION = re.compile(r"(?<![\w@])@([a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)+)")
# Same idea as twitter.py: an emoji sequence is one grapheme.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿](?:[️\U0001F3FB-\U0001F3FF]|"
    "‍[\U0001F000-\U0001FAFF☀-➿])*"
)


def length(text):
    """Approximate grapheme count (what Bluesky's 300 limit is measured in)."""
    text = _EMOJI.sub("￿", unicodedata.normalize("NFC", text))
    return sum(1 for ch in text if not unicodedata.combining(ch) and ch not in "‍️")


def missing(cfg, secrets):
    out = []
    if not cfg["bluesky"].get("handle"):
        out.append("bluesky handle")
    if not secrets.get("bluesky_app_password"):
        out.append("bluesky_app_password")
    return out


def _span(text, start, end):
    return {"byteStart": len(text[:start].encode()), "byteEnd": len(text[:end].encode())}


def facets(text, resolve_handle=lambda handle: None):
    out = []
    for m in _URL.finditer(text):
        url = m.group().rstrip(_TRAILING)
        out.append({"index": _span(text, m.start(), m.start() + len(url)),
                    "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}]})
    for m in _HASHTAG.finditer(text):
        if any(u.start() <= m.start() < u.end() for u in _URL.finditer(text)):
            continue  # a #fragment inside a link
        out.append({"index": _span(text, m.start(), m.end()),
                    "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": m.group(1)}]})
    for m in _MENTION.finditer(text):
        did = resolve_handle(m.group(1).rstrip("."))
        if did:
            out.append({"index": _span(text, m.start(), m.start() + 1 + len(m.group(1).rstrip("."))),
                        "features": [{"$type": "app.bsky.richtext.facet#mention", "did": did}]})
    return out


def post(text, cfg, secrets):
    service = cfg["bluesky"].get("service", "https://bsky.social").rstrip("/")
    session = http.request("POST", f"{service}/xrpc/com.atproto.server.createSession", json_body={
        "identifier": cfg["bluesky"]["handle"].lstrip("@"),
        "password": secrets.get("bluesky_app_password"),
    }).json()
    auth = {"Authorization": "Bearer " + session["accessJwt"]}

    def resolve(handle):
        try:
            return http.request(
                "GET", f"{service}/xrpc/com.atproto.identity.resolveHandle?"
                + urllib.parse.urlencode({"handle": handle}), headers=auth,
            ).json().get("did")
        except http.HTTPError:
            return None  # unknown handle: leave it as plain text

    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "createdAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    }
    if f := facets(text, resolve):
        record["facets"] = f
    created = http.request("POST", f"{service}/xrpc/com.atproto.repo.createRecord", headers=auth, json_body={
        "repo": session["did"], "collection": "app.bsky.feed.post", "record": record,
    }).json()
    rkey = created["uri"].rsplit("/", 1)[-1]
    return f"https://bsky.app/profile/{session.get('handle') or session['did']}/post/{rkey}"
