import base64
import datetime as dt
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from postr import config, core, http
from postr.platforms import blog, bluesky, linkedin, mastodon, twitter


class FakeSecrets:
    def __init__(self, **values):
        self.values = values

    def get(self, name):
        return self.values.get(name, "")

    def set(self, name, value):
        self.values[name] = value


class TwitterTest(unittest.TestCase):
    def test_oauth1_signature_matches_twitter_docs_example(self):
        # https://developer.x.com/en/docs/authentication/oauth-1-0a/creating-a-signature
        header = twitter.oauth1_header(
            "POST", "https://api.twitter.com/1.1/statuses/update.json",
            {"include_entities": "true", "status": "Hello Ladies + Gentlemen, a signed OAuth request!"},
            "xvz1evFS4wEEPTGEFPHBog", "kAcSOqF21Fu85e7zjz7ZN2U4ZRhfV3WpwPAoE3Z7kBw",
            "370773112-GmHxMAgYyLbNEtIKZeRNFsMKPR9EyMZeS9weJAEb", "LswwdoUaIvS8ltyTt5jkRh4J50vUPVVHtR2YPi5kE",
            nonce="kYjzVBB8Y0ZFabxSWbWovY3uYSQ2pTgmZeNu2VS4cg", timestamp=1318622958,
        )
        self.assertIn('oauth_signature="hCtSmYh%2BiHYCEqBWrE7C7hYmtUk%3D"', header)

    def test_weighted_length(self):
        self.assertEqual(twitter.length("hello"), 5)
        self.assertEqual(twitter.length("see https://example.com/a/very/long/path?x=1"), 4 + 23)
        self.assertEqual(twitter.length("日本"), 4)
        self.assertEqual(twitter.length("👍"), 2)
        self.assertEqual(twitter.length("👨‍👩‍👧"), 2)

    def test_post(self):
        secrets = FakeSecrets(**{k: "x" for k in twitter.SECRET_KEYS})
        with mock.patch.object(http, "request", return_value=http.Response(201, '{"data":{"id":"42","text":"hi"}}')) as req:
            self.assertEqual(twitter.post("hi", {}, secrets), "https://x.com/i/web/status/42")
        self.assertEqual(req.call_args.kwargs["json_body"], {"text": "hi"})
        self.assertTrue(req.call_args.kwargs["headers"]["Authorization"].startswith("OAuth "))


class LinkedInTest(unittest.TestCase):
    def test_escape_reserved_and_keep_hashtags(self):
        self.assertEqual(linkedin.escape("a (b) [c] *d* _e_ @f"), r"a \(b\) \[c\] \*d\* \_e\_ \@f")
        self.assertEqual(linkedin.escape("ship it #rust"), r"ship it {hashtag|\#|rust}")
        self.assertEqual(linkedin.escape("issue #12 and C#"), r"issue {hashtag|\#|12} and C\#")

    def test_api_version_defaults_to_two_months_back(self):
        cfg = {"linkedin": {"api_version": ""}}
        self.assertEqual(linkedin.api_version(cfg, dt.date(2026, 10, 7)), "202608")
        self.assertEqual(linkedin.api_version(cfg, dt.date(2026, 2, 1)), "202512")
        self.assertEqual(linkedin.api_version({"linkedin": {"api_version": "202601"}}), "202601")

    def test_post(self):
        cfg = json.loads(json.dumps(config.DEFAULTS))
        cfg["linkedin"]["author_urn"] = "urn:li:person:abc"
        resp = http.Response(201, "", {"x-restli-id": "urn:li:share:7"})
        with mock.patch.object(http, "request", return_value=resp) as req:
            url = linkedin.post("hello (world)", cfg, FakeSecrets(linkedin_access_token="t"))
        self.assertEqual(url, "https://www.linkedin.com/feed/update/urn:li:share:7/")
        body = req.call_args.kwargs["json_body"]
        self.assertEqual(body["author"], "urn:li:person:abc")
        self.assertEqual(body["commentary"], r"hello \(world\)")
        self.assertEqual(req.call_args.kwargs["headers"]["X-Restli-Protocol-Version"], "2.0.0")


class MastodonTest(unittest.TestCase):
    def test_length(self):
        self.assertEqual(mastodon.length("hi @alice@hostux.social see https://example.com/" + "a" * 50), 3 + 6 + 5 + 23)

    def test_post(self):
        cfg = json.loads(json.dumps(config.DEFAULTS))
        resp = http.Response(200, '{"url": "https://hostux.social/@me/1"}')
        with mock.patch.object(http, "request", return_value=resp) as req:
            url = mastodon.post("hi", cfg, FakeSecrets(mastodon_access_token="t"))
        self.assertEqual(url, "https://hostux.social/@me/1")
        self.assertEqual(req.call_args.args, ("POST", "https://hostux.social/api/v1/statuses"))
        self.assertEqual(req.call_args.kwargs["json_body"], {"status": "hi", "visibility": "public"})
        self.assertIn("Idempotency-Key", req.call_args.kwargs["headers"])

    def test_configurable_limit(self):
        cfg = json.loads(json.dumps(config.DEFAULTS))
        cfg["mastodon"]["max_characters"] = 1000
        secrets = FakeSecrets(mastodon_access_token="t")
        self.assertEqual(core.problems("x" * 900, ["mastodon"], cfg, secrets), {})


class BlueskyTest(unittest.TestCase):
    def test_length_counts_graphemes(self):
        self.assertEqual(bluesky.length("héllo"), 5)
        self.assertEqual(bluesky.length("e\u0301"), 1)
        self.assertEqual(bluesky.length("👨\u200d👩\u200d👧!"), 2)

    def test_facets_use_utf8_byte_offsets(self):
        text = "Café → https://rmpr.xyz/short/. #rust @alice.bsky.social and @nobody.example"
        resolve = {"alice.bsky.social": "did:plc:alice"}.get
        got = {f["features"][0]["$type"].rsplit("#", 1)[1]: f for f in bluesky.facets(text, resolve)}
        raw = text.encode()
        link = got["link"]
        self.assertEqual(link["features"][0]["uri"], "https://rmpr.xyz/short/")
        self.assertEqual(raw[link["index"]["byteStart"]:link["index"]["byteEnd"]], b"https://rmpr.xyz/short/")
        tag = got["tag"]
        self.assertEqual(raw[tag["index"]["byteStart"]:tag["index"]["byteEnd"]], b"#rust")
        self.assertEqual(tag["features"][0]["tag"], "rust")
        mention = got["mention"]
        self.assertEqual(raw[mention["index"]["byteStart"]:mention["index"]["byteEnd"]], b"@alice.bsky.social")
        self.assertEqual(len(bluesky.facets(text, resolve)), 3)  # unresolvable handle stays plain

    def test_no_hashtag_inside_url(self):
        self.assertEqual([f["features"][0]["$type"] for f in bluesky.facets("https://a.b/c#frag")],
                         ["app.bsky.richtext.facet#link"])

    def test_post(self):
        cfg = json.loads(json.dumps(config.DEFAULTS))
        cfg["bluesky"]["handle"] = "@me.bsky.social"
        responses = [
            http.Response(200, '{"accessJwt": "jwt", "did": "did:plc:me", "handle": "me.bsky.social"}'),
            http.Response(200, '{"uri": "at://did:plc:me/app.bsky.feed.post/3abc", "cid": "x"}'),
        ]
        with mock.patch.object(http, "request", side_effect=responses) as req:
            url = bluesky.post("hello", cfg, FakeSecrets(bluesky_app_password="pw"))
        self.assertEqual(url, "https://bsky.app/profile/me.bsky.social/post/3abc")
        login, create = req.call_args_list
        self.assertEqual(login.kwargs["json_body"], {"identifier": "me.bsky.social", "password": "pw"})
        body = create.kwargs["json_body"]
        self.assertEqual((body["repo"], body["collection"]), ("did:plc:me", "app.bsky.feed.post"))
        self.assertEqual(body["record"]["text"], "hello")
        self.assertNotIn("facets", body["record"])
        self.assertTrue(body["record"]["createdAt"].endswith("Z"))
        self.assertEqual(create.kwargs["headers"]["Authorization"], "Bearer jwt")


class BlogTest(unittest.TestCase):
    def test_render(self):
        now = dt.datetime(2026, 10, 7, 10, 30, 5, tzinfo=dt.timezone(dt.timedelta(hours=2)))
        name, content = blog.render('Shipped **postr**: "write-only" [posting](https://rmpr.xyz)\n\nMore.', now)
        self.assertEqual(name, "2026-10-07-083005")
        self.assertEqual(content, (
            '---\ntitle: "Shipped postr: \\"write-only\\" posting"\n'
            "date: 2026-10-07 10:30:05 +0200\n---\n\n"
            'Shipped **postr**: "write-only" [posting](https://rmpr.xyz)\n\nMore.\n'
        ))

    def test_title_is_truncated_on_a_word(self):
        self.assertEqual(blog.title_for("word " * 30), ("word " * 14).strip() + "…")

    def test_post_commits_file(self):
        cfg = json.loads(json.dumps(config.DEFAULTS))
        now = dt.datetime(2026, 10, 7, 8, 0, 0, tzinfo=dt.timezone.utc)
        with mock.patch.object(http, "request", return_value=http.Response(201, "{}")) as req:
            url = blog.post("hi", cfg, FakeSecrets(github_token="g"), now=now)
        self.assertEqual(url, "https://rmpr.xyz/short/2026-10-07-080000/")
        method, endpoint = req.call_args.args
        self.assertEqual((method, endpoint), ("PUT", "https://api.github.com/repos/RMPR/rmpr.github.io/contents/_shorts/2026-10-07-080000.md"))
        body = req.call_args.kwargs["json_body"]
        self.assertEqual(body["branch"], "master")
        self.assertIn("hi\n", base64.b64decode(body["content"]).decode())


class CoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch.object(config, "DATA_DIR", Path(self.tmp.name))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_problems(self):
        cfg = json.loads(json.dumps(config.DEFAULTS))
        self.assertEqual(core.problems("  ", ["blog"], cfg, FakeSecrets()), {"*": ["nothing to post"]})
        issues = core.problems("x" * 300, ["twitter", "blog"], cfg, FakeSecrets(github_token="g"))
        self.assertEqual(list(issues), ["twitter"])
        self.assertIn("20 characters over the limit", issues["twitter"])

    def test_publish_isolates_failures_and_logs(self):
        ok = mock.Mock(post=mock.Mock(return_value="https://ok"))
        bad = mock.Mock(post=mock.Mock(side_effect=http.HTTPError(403, '{"detail":"nope"}', "u")))
        results = core.publish("hi", ["a", "b"], {}, FakeSecrets(), platforms={"a": ok, "b": bad})
        self.assertEqual([(r.platform, r.ok) for r in results], [("a", True), ("b", False)])
        self.assertEqual(results[1].error, "HTTP 403: nope")
        entry = json.loads((Path(self.tmp.name) / "history.jsonl").read_text())
        self.assertEqual(entry["results"], {"a": "https://ok", "b": "error: HTTP 403: nope"})


class ConfigTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as d, \
                mock.patch.object(config, "CONFIG_DIR", Path(d)), \
                mock.patch.object(config, "CONFIG_FILE", Path(d) / "config.toml"):
            cfg = config.load()
            cfg["blog"]["branch"] = 'we"ird'
            cfg["ui"]["targets"] = ["blog"]
            config.save(cfg)
            self.assertEqual(config.load(), cfg)

    def test_env_overrides_keyring(self):
        with mock.patch.dict(os.environ, {"POSTR_GITHUB_TOKEN": "env"}):
            self.assertEqual(config.SecretStore(tool="/nonexistent").get("github_token"), "env")


if __name__ == "__main__":
    unittest.main()
