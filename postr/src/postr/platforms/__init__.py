"""One module per destination. Each exposes NAME, LABEL, LIMIT,
length(text) -> int, missing(cfg, secrets) -> [str] and
post(text, cfg, secrets) -> url. A module may define limit(cfg) when its
limit is configurable."""

from . import blog, bluesky, linkedin, mastodon, twitter

PLATFORMS = {m.NAME: m for m in (twitter, mastodon, bluesky, linkedin, blog)}


def limit(platform, cfg):
    return platform.limit(cfg) if hasattr(platform, "limit") else platform.LIMIT
