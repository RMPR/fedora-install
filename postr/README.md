# postr

A write-only desktop app for posting to **X**, **LinkedIn** and the
**short form** section of [rmpr.xyz](https://rmpr.xyz/short/). You get a text
box, a toggle per platform with a character counter, and a Post button. It
has no timeline, notifications or replies, so there's nothing to scroll.

- `Ctrl+Enter` posts, `Ctrl+,` opens Preferences, `Ctrl+Q` quits.
- Platforms are posted to in parallel. If one fails, the others are
  unselected and your text stays, so posting again only retries the failure.
- The draft is autosaved (`~/.local/state/postr/draft.md`). Everything you
  post is logged locally to `~/.local/share/postr/history.jsonl`.
- Tokens are stored in the GNOME keyring (via `secret-tool`), never in files.
  Other settings are in `~/.config/postr/config.toml`.

GTK 4 + libadwaita, Python standard library only (no pip dependencies).

## Install

```sh
./install.sh   # installs deps with dnf if needed, then postr into ~/.local
```

## Setup

Open **Preferences** from the menu (or run `postr setup` in a terminal).

**X**: create a project/app at <https://developer.x.com>. Set the app's user
authentication permissions to *Read and write*, then generate the API key and
secret, plus an access token and secret for your account. Regenerate the
access token after changing permissions, because old tokens stay read-only.
Posting through the API may need a paid or pay-per-use plan.

**LinkedIn**: create an app at <https://www.linkedin.com/developers/apps>
and add the products *Share on LinkedIn* and *Sign In with LinkedIn using
OpenID Connect*. Under Auth, add `http://localhost:8723/callback` as a
redirect URL. Put the client ID and secret into postr and click **Connect**:
a browser tab opens, you approve, and you're done. The token lasts about 60
days, and Preferences shows when it expires. postr sends the
`LinkedIn-Version` header for two months before the current month. To pin a
specific version instead, set `api_version = "YYYYMM"` under `[linkedin]` in
the config.

**Blog**: create a [fine-grained token](https://github.com/settings/personal-access-tokens/new)
limited to `RMPR/rmpr.github.io`, with *Contents: Read and write*. Each
post becomes `_shorts/<UTC timestamp>.md` on `master`, and GitHub Pages
publishes it at `https://rmpr.xyz/short/<timestamp>/` within about a
minute. Markdown works.

## Command line

```sh
postr                                    # open the window
postr post "Hello"                       # post to the platforms selected in the window
postr post --to blog,linkedin "Hello"
echo "Hello" | postr post -              # read from stdin
postr post -n "Hello"                    # dry run: check lengths and credentials
postr status                             # what's configured
postr linkedin-login                     # refresh the LinkedIn token
```

Any secret can come from the environment instead of the keyring:
`POSTR_GITHUB_TOKEN`, `POSTR_TWITTER_API_KEY`, `POSTR_LINKEDIN_ACCESS_TOKEN`, …

## Tests

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```
