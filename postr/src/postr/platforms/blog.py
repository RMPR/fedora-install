"""rmpr.xyz short form: commit a file to the blog's _shorts collection through
the GitHub contents API. GitHub Pages rebuilds the site on push.

Needs a fine-grained GitHub token with "Contents: Read and write" on the blog
repository only.
"""

import base64
import datetime as dt
import json
import re

from .. import http

NAME = "blog"
LABEL = "Blog"
LIMIT = None


def length(text):
    return len(text)


def missing(cfg, secrets):
    return [] if secrets.get("github_token") else ["github_token"]


def title_for(text, width=70):
    """A plain-text title for the page <title> and the feed; not shown on the page."""
    line = next((l.strip() for l in text.splitlines() if l.strip()), "Short")
    line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)  # [text](url) -> text
    line = re.sub(r"[*_`#>]+", "", line).strip() or "Short"
    if len(line) > width:
        line = line[:width].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return line


def render(text, now):
    """Return (filename, file content) for a short posted at `now` (aware datetime)."""
    name = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    front = (
        "---\n"
        f"title: {json.dumps(title_for(text), ensure_ascii=False)}\n"
        f"date: {now.strftime('%Y-%m-%d %H:%M:%S %z')}\n"
        "---\n\n"
    )
    return name, front + text.strip() + "\n"


def post(text, cfg, secrets, now=None):
    b = cfg["blog"]
    now = now or dt.datetime.now().astimezone()
    name, content = render(text, now)
    path = f"{b['directory'].strip('/')}/{name}.md"
    http.request(
        "PUT", f"https://api.github.com/repos/{b['repo']}/contents/{path}",
        headers={
            "Authorization": "Bearer " + secrets.get("github_token"),
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json_body={
            "message": f"Short: {title_for(text)}",
            "content": base64.b64encode(content.encode()).decode(),
            "branch": b["branch"],
        },
    )
    return f"{b['site_url'].rstrip('/')}/short/{name}/"
