"""LinkedIn via the versioned Posts API (POST /rest/posts).

Needs a LinkedIn developer app with the "Share on LinkedIn" and "Sign In with
LinkedIn using OpenID Connect" products, and http://localhost:<port>/callback
as an authorized redirect URL. `login()` runs the 3-legged OAuth flow in your
browser once; the resulting token is valid for about 60 days.
"""

import datetime as dt
import http.server
import re
import secrets as _secrets
import time
import urllib.parse
import webbrowser

from .. import http as h

NAME = "linkedin"
LABEL = "LinkedIn"
LIMIT = 3000
AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
USERINFO_URL = "https://api.linkedin.com/v2/userinfo"
POSTS_URL = "https://api.linkedin.com/rest/posts"
SCOPES = "openid profile w_member_social"

# Characters reserved by LinkedIn's "little text" format must be escaped,
# otherwise the post is rejected or silently truncated.
_RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")
_HASHTAG = re.compile(r"(?<![\w#])#(\w+)")


def length(text):
    return len(text)


def escape(text):
    """Escape commentary, keeping #hashtags as real LinkedIn hashtags."""
    out, last = [], 0
    for m in _HASHTAG.finditer(text):
        out.append(_RESERVED.sub(r"\\\1", text[last:m.start()]))
        out.append("{hashtag|\\#|" + _RESERVED.sub(r"\\\1", m.group(1)) + "}")
        last = m.end()
    out.append(_RESERVED.sub(r"\\\1", text[last:]))
    return "".join(out)


def api_version(cfg, today=None):
    """LinkedIn-Version header. Versions live about a year, so default to the
    version from two months ago: recent, and certainly already released."""
    if cfg["linkedin"].get("api_version"):
        return str(cfg["linkedin"]["api_version"])
    today = today or dt.date.today()
    month = today.year * 12 + today.month - 1 - 2
    return f"{month // 12}{month % 12 + 1:02d}"


def missing(cfg, secrets):
    out = []
    if not secrets.get("linkedin_access_token") or not cfg["linkedin"].get("author_urn"):
        out.append("linkedin login")
    elif cfg["linkedin"].get("token_expires_at", 0) and cfg["linkedin"]["token_expires_at"] < time.time():
        out.append("linkedin login (token expired)")
    return out


def post(text, cfg, secrets):
    body = {
        "author": cfg["linkedin"]["author_urn"],
        "commentary": escape(text),
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    resp = h.request("POST", POSTS_URL, json_body=body, headers={
        "Authorization": "Bearer " + secrets.get("linkedin_access_token"),
        "LinkedIn-Version": api_version(cfg),
        "X-Restli-Protocol-Version": "2.0.0",
    })
    urn = resp.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/update/{urn}/" if urn else "https://www.linkedin.com/in/me/recent-activity/all/"


def login(cfg, store, open_url=webbrowser.open, timeout=300):
    """Run the OAuth flow; store the token in the keyring and the author URN in cfg."""
    client_id = cfg["linkedin"].get("client_id")
    client_secret = store.get("linkedin_client_secret")
    if not client_id or not client_secret:
        raise RuntimeError("Set the LinkedIn client ID and client secret first")
    port = int(cfg["linkedin"].get("redirect_port", 8723))
    redirect = f"http://localhost:{port}/callback"
    state = _secrets.token_urlsafe(16)
    result = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            if q.get("state", [""])[0] == state:
                result.update({k: v[0] for k, v in q.items()})
            ok = "code" in result
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(("postr is connected to LinkedIn, you can close this tab."
                              if ok else "LinkedIn login failed, check postr.").encode())

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 1
    try:
        open_url(AUTH_URL + "?" + urllib.parse.urlencode({
            "response_type": "code", "client_id": client_id,
            "redirect_uri": redirect, "state": state, "scope": SCOPES,
        }))
        deadline = time.time() + timeout
        while not result and time.time() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if "code" not in result:
        raise RuntimeError(result.get("error_description") or "LinkedIn login timed out")

    token = h.request("POST", TOKEN_URL, data=urllib.parse.urlencode({
        "grant_type": "authorization_code", "code": result["code"],
        "redirect_uri": redirect, "client_id": client_id, "client_secret": client_secret,
    }), headers={"Content-Type": "application/x-www-form-urlencoded"}).json()
    access = token["access_token"]
    me = h.request("GET", USERINFO_URL, headers={"Authorization": "Bearer " + access}).json()

    store.set("linkedin_access_token", access)
    cfg["linkedin"]["author_urn"] = "urn:li:person:" + me["sub"]
    cfg["linkedin"]["token_expires_at"] = int(time.time()) + int(token.get("expires_in", 0))
    return me.get("name", me["sub"])
