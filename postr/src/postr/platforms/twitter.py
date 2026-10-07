"""X (Twitter) via API v2 POST /2/tweets, signed with OAuth 1.0a user context.

Credentials come from an app in the X developer portal with "Read and write"
permission: API key/secret plus an access token/secret for your own account.
"""

import base64
import hashlib
import hmac
import re
import secrets as _secrets
import time
import unicodedata
import urllib.parse

from .. import http

NAME = "twitter"
LABEL = "X"
LIMIT = 280
ENDPOINT = "https://api.x.com/2/tweets"
SECRET_KEYS = ("twitter_api_key", "twitter_api_secret", "twitter_access_token", "twitter_access_secret")

# twitter-text v3: code points in these ranges weigh 1, everything else 2,
# and any URL weighs 23 whatever its real length.
_LIGHT = ((0, 4351), (8192, 8205), (8208, 8223), (8242, 8247))
_URL = re.compile(r"https?://\S+", re.IGNORECASE)
# An emoji with its modifiers / ZWJ-joined parts weighs 2 in total.
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF☀-➿](?:[️\U0001F3FB-\U0001F3FF]|"
    "‍[\U0001F000-\U0001FAFF☀-➿])*"
)


def length(text):
    """Approximation of X's weighted length (close enough for a counter)."""
    text = unicodedata.normalize("NFC", text)
    n = 23 * len(_URL.findall(text))
    for chunk in _URL.split(text):
        for ch in _EMOJI.sub("￿", chunk):
            cp = ord(ch)
            n += 1 if any(lo <= cp <= hi for lo, hi in _LIGHT) else 2
    return n


def missing(cfg, secrets):
    return [k for k in SECRET_KEYS if not secrets.get(k)]


def _pct(s):
    return urllib.parse.quote(str(s), safe="~-._")


def oauth1_header(method, url, params, consumer_key, consumer_secret,
                  token, token_secret, nonce=None, timestamp=None):
    """Build an OAuth 1.0a HMAC-SHA1 Authorization header (RFC 5849).

    `params` are the query/form parameters that take part in the signature;
    a JSON body does not.
    """
    oauth = {
        "oauth_consumer_key": consumer_key,
        "oauth_nonce": nonce or _secrets.token_hex(16),
        "oauth_signature_method": "HMAC-SHA1",
        "oauth_timestamp": str(timestamp or int(time.time())),
        "oauth_token": token,
        "oauth_version": "1.0",
    }
    pairs = sorted((_pct(k), _pct(v)) for k, v in {**params, **oauth}.items())
    param_str = "&".join(f"{k}={v}" for k, v in pairs)
    base = "&".join((method.upper(), _pct(url), _pct(param_str)))
    key = f"{_pct(consumer_secret)}&{_pct(token_secret)}"
    sig = hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()
    oauth["oauth_signature"] = base64.b64encode(sig).decode()
    return "OAuth " + ", ".join(f'{_pct(k)}="{_pct(v)}"' for k, v in sorted(oauth.items()))


def post(text, cfg, secrets):
    s = {k: secrets.get(k) for k in SECRET_KEYS}
    auth = oauth1_header(
        "POST", ENDPOINT, {},
        s["twitter_api_key"], s["twitter_api_secret"],
        s["twitter_access_token"], s["twitter_access_secret"],
    )
    resp = http.request("POST", ENDPOINT, headers={"Authorization": auth}, json_body={"text": text})
    tweet_id = resp.json()["data"]["id"]
    return f"https://x.com/i/web/status/{tweet_id}"
