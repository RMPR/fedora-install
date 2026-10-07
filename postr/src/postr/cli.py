"""Command line entry point. `postr` with no arguments opens the window."""

import argparse
import getpass
import sys

from . import config, core
from .platforms import PLATFORMS, linkedin

# (section, key, prompt) for the non-secret settings `postr setup` asks about.
SETTINGS = {
    "linkedin": [("linkedin", "client_id", "LinkedIn client ID")],
    "blog": [
        ("blog", "repo", "Blog repository (owner/name)"),
        ("blog", "branch", "Blog branch"),
        ("blog", "site_url", "Blog URL"),
    ],
}
SECRET_PROMPTS = {
    "twitter_api_key": "X API key (consumer key)",
    "twitter_api_secret": "X API key secret",
    "twitter_access_token": "X access token",
    "twitter_access_secret": "X access token secret",
    "linkedin_client_secret": "LinkedIn client secret",
    "github_token": "GitHub fine-grained token (Contents: read/write on the blog repo)",
}


def cmd_post(args, cfg, store):
    text = sys.stdin.read().rstrip("\n") if args.text in (None, "-") else args.text
    targets = args.to.split(",") if args.to else cfg["ui"]["targets"]
    unknown = [t for t in targets if t not in PLATFORMS]
    if unknown:
        sys.exit(f"unknown platform(s): {', '.join(unknown)} (choose from {', '.join(PLATFORMS)})")
    secrets = core.CachedSecrets(store)
    issues = core.problems(text, targets, cfg, secrets)
    for name, msgs in issues.items():
        print(f"{name}: {'; '.join(msgs)}", file=sys.stderr)
    if issues:
        sys.exit(2)
    if args.dry_run:
        for t in targets:
            p = PLATFORMS[t]
            print(f"{p.LABEL}: {p.length(text)}" + (f"/{p.LIMIT}" if p.LIMIT else "") + " characters, ok")
        return
    failed = False
    for r in core.publish(text, targets, cfg, secrets):
        label = PLATFORMS[r.platform].LABEL
        print(f"{label}: {r.url}" if r.ok else f"{label}: FAILED {r.error}", file=sys.stdout if r.ok else sys.stderr)
        failed |= not r.ok
    sys.exit(1 if failed else 0)


def cmd_setup(args, cfg, store):
    unknown = [p for p in args.platforms if p not in PLATFORMS]
    if unknown:
        sys.exit(f"unknown platform(s): {', '.join(unknown)}")
    for platform in args.platforms or list(PLATFORMS):
        print(f"== {PLATFORMS[platform].LABEL} (leave empty to keep the current value)")
        for section, key, prompt in SETTINGS.get(platform, []):
            value = input(f"{prompt} [{cfg[section].get(key, '')}]: ").strip()
            if value:
                cfg[section][key] = value
        for key in config.SECRETS[platform]:
            if key == "linkedin_access_token":
                continue  # comes from `postr linkedin-login`
            have = " [set]" if store.get(key) else ""
            value = getpass.getpass(f"{SECRET_PROMPTS[key]}{have}: ").strip()
            if value:
                store.set(key, value)
        config.save(cfg)
        if platform == "linkedin" and input("Log in to LinkedIn now? [Y/n] ").strip().lower() != "n":
            cmd_linkedin_login(args, cfg, store)


def cmd_linkedin_login(args, cfg, store):
    print("Opening LinkedIn in your browser…")
    name = linkedin.login(cfg, store)
    config.save(cfg)
    print(f"Connected as {name}.")


def cmd_status(args, cfg, store):
    secrets = core.CachedSecrets(store)
    for name, p in PLATFORMS.items():
        missing = p.missing(cfg, secrets)
        print(f"{p.LABEL:9} {'ready' if not missing else 'needs: ' + ', '.join(missing)}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="postr", description="Write-only posting to X, LinkedIn and the blog.")
    sub = parser.add_subparsers(dest="cmd")
    p = sub.add_parser("post", help="post text (or stdin with '-')")
    p.add_argument("text", nargs="?")
    p.add_argument("--to", help=f"comma separated, from: {','.join(PLATFORMS)}")
    p.add_argument("-n", "--dry-run", action="store_true", help="check lengths and credentials only")
    p = sub.add_parser("setup", help="enter credentials")
    p.add_argument("platforms", nargs="*", metavar="platform", help=f"any of: {', '.join(PLATFORMS)}")
    sub.add_parser("linkedin-login", help="(re)connect LinkedIn in the browser")
    sub.add_parser("status", help="show which platforms are configured")
    args = parser.parse_args(argv)

    if args.cmd is None:
        from .gui import run
        return run()

    cfg, store = config.load(), config.SecretStore()
    try:
        {"post": cmd_post, "setup": cmd_setup, "linkedin-login": cmd_linkedin_login,
         "status": cmd_status}[args.cmd](args, cfg, store)
    except (RuntimeError, KeyboardInterrupt) as exc:
        sys.exit(str(exc) or "aborted")


if __name__ == "__main__":
    main()
