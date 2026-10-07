"""Settings (plain TOML) and secrets (GNOME keyring via secret-tool).

Non-secret settings live in ~/.config/postr/config.toml. Tokens live in the
keyring under service=postr, key=<name>. Any secret can be overridden with an
environment variable, POSTR_<NAME> (e.g. POSTR_GITHUB_TOKEN), which is handy
for scripting and for machines without a keyring.
"""

import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path


def _xdg(var, default):
    return Path(os.environ.get(var) or Path.home() / default) / "postr"


CONFIG_DIR = _xdg("XDG_CONFIG_HOME", ".config")
DATA_DIR = _xdg("XDG_DATA_HOME", ".local/share")
STATE_DIR = _xdg("XDG_STATE_HOME", ".local/state")
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULTS = {
    "blog": {
        "repo": "RMPR/rmpr.github.io",
        "branch": "master",
        "directory": "_shorts",
        "site_url": "https://rmpr.xyz",
    },
    "linkedin": {
        "client_id": "",
        "author_urn": "",
        "token_expires_at": 0,
        # Empty means "pick a recent version automatically", see linkedin.py.
        "api_version": "",
        "redirect_port": 8723,
    },
    "twitter": {},
    "mastodon": {"instance": "https://hostux.social", "visibility": "public", "max_characters": 500},
    "bluesky": {"handle": "", "service": "https://bsky.social"},
    "ui": {"targets": ["twitter", "mastodon", "bluesky", "linkedin", "blog"]},
}

SECRETS = {
    "twitter": ["twitter_api_key", "twitter_api_secret", "twitter_access_token", "twitter_access_secret"],
    "mastodon": ["mastodon_access_token"],
    "bluesky": ["bluesky_app_password"],
    "linkedin": ["linkedin_client_secret", "linkedin_access_token"],
    "blog": ["github_token"],
}


def load():
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if CONFIG_FILE.exists():
        with CONFIG_FILE.open("rb") as f:
            for section, values in tomllib.load(f).items():
                cfg.setdefault(section, {}).update(values)
    return cfg


def _toml_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_toml_value(x) for x in v) + "]"
    return json.dumps(str(v))  # JSON strings are valid TOML basic strings


def save(cfg):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for section, values in cfg.items():
        lines.append(f"[{section}]")
        lines += [f"{k} = {_toml_value(v)}" for k, v in values.items()]
        lines.append("")
    CONFIG_FILE.write_text("\n".join(lines))


class SecretStore:
    """Keyring access through secret-tool (ships with libsecret on Fedora)."""

    def __init__(self, tool=None):
        self.tool = tool or shutil.which("secret-tool")

    def get(self, name):
        env = os.environ.get("POSTR_" + name.upper())
        if env:
            return env
        if not self.tool:
            return ""
        out = subprocess.run(
            [self.tool, "lookup", "service", "postr", "key", name],
            capture_output=True, text=True,
        )
        return out.stdout.strip() if out.returncode == 0 else ""

    def set(self, name, value):
        if not self.tool:
            raise RuntimeError(
                "secret-tool not found; install libsecret or set POSTR_" + name.upper()
            )
        if not value:
            subprocess.run([self.tool, "clear", "service", "postr", "key", name], check=False)
            return
        subprocess.run(
            [self.tool, "store", f"--label=postr {name}", "service", "postr", "key", name],
            input=value, text=True, check=True,
        )
