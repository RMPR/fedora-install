"""One module per destination. Each exposes NAME, LABEL, LIMIT,
length(text) -> int, missing(cfg, secrets) -> [str] and
post(text, cfg, secrets) -> url."""

from . import blog, linkedin, twitter

PLATFORMS = {m.NAME: m for m in (twitter, linkedin, blog)}
