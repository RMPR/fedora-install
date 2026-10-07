"""GTK 4 / libadwaita window: a text box, a checkbox per platform, a Post button.

There is deliberately nothing to read here: no timeline, no notifications,
no replies. Ctrl+Enter posts.
"""

import html
import threading
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, __version__, config, core  # noqa: E402
from .platforms import PLATFORMS, limit, linkedin  # noqa: E402

CSS = """
.postr-editor { font-size: 1.2em; background: transparent; }
.postr-count { font-feature-settings: "tnum"; opacity: 0.7; }
.postr-results { padding: 0 18px; }
"""

DRAFT = config.STATE_DIR / "draft.md"


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="postr", default_width=720, default_height=440)
        self.cfg = config.load()
        self.store = config.SecretStore()
        self.checks = {}
        self.counts = {}
        self._save_source = 0
        self._auto_check = False  # set while postr itself flips checkboxes

        self.toasts = Adw.ToastOverlay()
        view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("About postr", "app.about")
        header.pack_end(Gtk.MenuButton(icon_name="open-menu-symbolic", menu_model=menu, tooltip_text="Menu"))
        view.add_top_bar(header)

        self.buffer = Gtk.TextBuffer()
        self.editor = Gtk.TextView(
            buffer=self.buffer, wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=18, bottom_margin=18, left_margin=18, right_margin=18,
        )
        self.editor.add_css_class("postr-editor")
        self.editor.update_property([Gtk.AccessibleProperty.LABEL], ["Post text"])
        scroller = Gtk.ScrolledWindow(child=self.editor, vexpand=True)

        self.results = Gtk.Label(xalign=0, wrap=True, use_markup=True, visible=False)
        self.results.add_css_class("postr-results")

        bar = Gtk.Box(spacing=6, margin_top=6, margin_bottom=12, margin_start=12, margin_end=12)
        # One checkbox per platform; wraps onto more rows when the window is narrow.
        where = Gtk.FlowBox(selection_mode=Gtk.SelectionMode.NONE, hexpand=True,
                            max_children_per_line=len(PLATFORMS), column_spacing=12, row_spacing=2,
                            valign=Gtk.Align.CENTER)
        where.update_property([Gtk.AccessibleProperty.LABEL], ["Where to post"])
        selected = set(self.cfg["ui"].get("targets", PLATFORMS))
        for name, p in PLATFORMS.items():
            count = Gtk.Label()
            count.add_css_class("postr-count")
            box = Gtk.Box(spacing=6)
            box.append(Gtk.Label(label=p.LABEL))
            box.append(count)
            check = Gtk.CheckButton(child=box, active=name in selected, tooltip_text=f"Post to {p.LABEL}")
            check.connect("toggled", self.on_targets_changed)
            where.append(check)
            self.checks[name], self.counts[name] = check, count
        bar.append(where)
        self.spinner = Gtk.Spinner()
        bar.append(self.spinner)
        self.post_button = Gtk.Button(label="Post", tooltip_text="Post (Ctrl+Enter)", valign=Gtk.Align.CENTER)
        self.post_button.add_css_class("suggested-action")
        self.post_button.connect("clicked", lambda *_: self.post())
        bar.append(self.post_button)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content.append(scroller)
        content.append(self.results)
        content.append(bar)
        view.set_content(content)
        self.toasts.set_child(view)
        self.set_content(self.toasts)

        # Capture phase so Ctrl+Enter posts instead of inserting a newline.
        keys = Gtk.ShortcutController(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        keys.add_shortcut(Gtk.Shortcut(
            trigger=Gtk.ShortcutTrigger.parse_string("<Control>Return|<Control>KP_Enter"),
            action=Gtk.CallbackAction.new(lambda *_: self.post() or True),
        ))
        self.add_controller(keys)

        if DRAFT.exists():
            self.buffer.set_text(DRAFT.read_text())
        self.buffer.connect("changed", self.on_text_changed)
        self.on_text_changed()
        self.editor.grab_focus()

    # -- state ------------------------------------------------------------

    @property
    def text(self):
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), False)

    def targets(self):
        return [n for n, t in self.checks.items() if t.get_active()]

    def on_text_changed(self, *_):
        text = self.text
        over = False
        for name, p in PLATFORMS.items():
            n = p.length(text)
            label = self.counts[name]
            lim = limit(p, self.cfg)
            label.set_text(f"{n}/{lim}" if lim else str(n))
            too_long = bool(lim and n > lim)
            (label.add_css_class if too_long else label.remove_css_class)("error")
            over |= too_long and self.checks[name].get_active()
        self.post_button.set_sensitive(bool(text.strip()) and bool(self.targets()) and not over)
        if not self._save_source:
            self._save_source = GLib.timeout_add(500, self.save_draft)

    def on_targets_changed(self, *_):
        if not self._auto_check:
            self.cfg["ui"]["targets"] = self.targets()
            config.save(self.cfg)
        self.on_text_changed()

    def set_targets(self, names):
        self._auto_check = True
        for name, toggle in self.checks.items():
            toggle.set_active(name in names)
        self._auto_check = False

    def save_draft(self):
        self._save_source = 0
        try:
            DRAFT.parent.mkdir(parents=True, exist_ok=True)
            if self.text.strip():
                DRAFT.write_text(self.text)
            elif DRAFT.exists():
                DRAFT.unlink()
        except OSError:
            pass
        return GLib.SOURCE_REMOVE

    # -- posting ----------------------------------------------------------

    def set_busy(self, busy):
        self.editor.set_editable(not busy)
        self.spinner.set_spinning(busy)
        for t in self.checks.values():
            t.set_sensitive(not busy)
        if busy:
            self.post_button.set_sensitive(False)
        else:
            self.on_text_changed()

    def post(self):
        if not self.post_button.get_sensitive():
            return
        text, targets = self.text, self.targets()
        self.set_busy(True)
        self.results.set_visible(False)

        def work():
            secrets = core.CachedSecrets(self.store)
            issues = core.problems(text, targets, self.cfg, secrets)
            if issues:
                GLib.idle_add(self.on_problems, issues)
            else:
                GLib.idle_add(self.on_done, text, core.publish(text, targets, self.cfg, secrets))

        threading.Thread(target=work, daemon=True).start()

    def on_problems(self, issues):
        self.set_busy(False)
        lines = [f"<b>{PLATFORMS[n].LABEL if n in PLATFORMS else 'Post'}</b>: needs "
                 f"{html.escape(', '.join(m))}" for n, m in issues.items()]
        self.show_results(lines + ["Open <b>Preferences</b> from the menu to fix this."])
        toast = Adw.Toast(title="Not posted: setup incomplete", button_label="Preferences")
        toast.set_action_name("app.preferences")
        self.toasts.add_toast(toast)

    def on_done(self, text, results):
        failed = [r for r in results if not r.ok]
        lines = []
        for r in results:
            label = PLATFORMS[r.platform].LABEL
            if r.ok:
                lines.append(f'<b>{label}</b>: <a href="{html.escape(r.url)}">{html.escape(r.url)}</a>')
            else:
                lines.append(f"<b>{label}</b>: <span foreground='#e01b24'>{html.escape(r.error)}</span>")
        if failed:
            # Leave only what failed selected, so retrying can't double post.
            self.set_targets([r.platform for r in failed])
        else:
            self.set_targets(self.cfg["ui"]["targets"])  # back to the usual selection
            if self.text == text:
                self.buffer.set_text("")
        self.set_busy(False)
        self.show_results(lines)
        self.toasts.add_toast(Adw.Toast(
            title="Posted" if not failed else
            f"Failed on {', '.join(PLATFORMS[r.platform].LABEL for r in failed)}; fix and post again",
            timeout=4 if not failed else 8,
        ))

    def show_results(self, lines):
        self.results.set_markup("\n".join(lines))
        self.results.set_visible(True)


class Preferences(Adw.PreferencesDialog):
    def __init__(self, win):
        super().__init__(title="Preferences")
        self.win, self.cfg, self.store = win, win.cfg, win.store
        self.fields = []  # [row, config section or None for a secret, key, saved value]
        page = Adw.PreferencesPage()
        self.add(page)

        g = Adw.PreferencesGroup(
            title="X",
            description="From an app in the X developer portal with Read and write permission.",
        )
        for key, title in (("twitter_api_key", "API key"), ("twitter_api_secret", "API key secret"),
                           ("twitter_access_token", "Access token"), ("twitter_access_secret", "Access token secret")):
            self.secret_row(g, key, title)
        page.add(g)

        g = Adw.PreferencesGroup(
            title="Mastodon",
            description="On your instance: Preferences → Development → New application, "
                        "with only the write:statuses scope. Paste “Your access token”.",
        )
        self.setting_row(g, "mastodon", "instance", "Instance")
        self.secret_row(g, "mastodon_access_token", "Access token")
        page.add(g)

        g = Adw.PreferencesGroup(
            title="Bluesky",
            description="Settings → Privacy and security → App passwords. Never your main password.",
        )
        self.setting_row(g, "bluesky", "handle", "Handle")
        self.secret_row(g, "bluesky_app_password", "App password")
        page.add(g)

        port = self.cfg["linkedin"].get("redirect_port", 8723)
        g = Adw.PreferencesGroup(
            title="LinkedIn",
            description=("App with the “Share on LinkedIn” and “Sign In with LinkedIn using OpenID "
                         f"Connect” products, and http://localhost:{port}/callback as redirect URL."),
        )
        self.setting_row(g, "linkedin", "client_id", "Client ID")
        self.secret_row(g, "linkedin_client_secret", "Client secret")
        self.account = Adw.ActionRow(title="Account")
        connect = Gtk.Button(label="Connect", valign=Gtk.Align.CENTER)
        connect.connect("clicked", self.on_linkedin_connect)
        self.account.add_suffix(connect)
        g.add(self.account)
        self.update_account()
        page.add(g)

        g = Adw.PreferencesGroup(
            title="Blog",
            description="Short posts are committed to the blog repository. "
                        "Use a fine-grained token with Contents: read and write on that repository only.",
        )
        self.setting_row(g, "blog", "repo", "Repository")
        self.setting_row(g, "blog", "branch", "Branch")
        self.setting_row(g, "blog", "site_url", "Site URL")
        self.secret_row(g, "github_token", "GitHub token")
        page.add(g)

        self.connect("closed", lambda *_: self.save())

    def setting_row(self, group, section, key, title):
        value = str(self.cfg[section].get(key, ""))
        row = Adw.EntryRow(title=title, text=value)
        group.add(row)
        self.fields.append([row, section, key, value])

    def secret_row(self, group, key, title):
        value = self.store.get(key)
        row = Adw.PasswordEntryRow(title=title, text=value)
        group.add(row)
        self.fields.append([row, None, key, value])

    def save(self):
        for field in self.fields:
            row, section, key, saved = field
            value = row.get_text().strip()
            if value == saved:
                continue
            if section:
                self.cfg[section][key] = value
            else:
                try:
                    self.store.set(key, value)
                except Exception as exc:  # noqa: BLE001
                    self.win.toasts.add_toast(Adw.Toast(title=f"Couldn't save {key}: {exc}"))
                    continue
            field[3] = value
        config.save(self.cfg)

    def update_account(self, status=None):
        expires = self.cfg["linkedin"].get("token_expires_at", 0)
        if status:
            self.account.set_subtitle(status)
        elif not self.cfg["linkedin"].get("author_urn"):
            self.account.set_subtitle("Not connected")
        elif expires and expires < time.time():
            self.account.set_subtitle("Token expired, connect again")
        else:
            days = int((expires - time.time()) // 86400) if expires else None
            self.account.set_subtitle("Connected" + (f", token valid for {days} more days" if days is not None else ""))

    def on_linkedin_connect(self, button):
        self.save()
        button.set_sensitive(False)
        self.update_account("Waiting for the browser…")

        def work():
            try:
                name = linkedin.login(self.cfg, self.store, open_url=self.open_uri)
                config.save(self.cfg)
                msg = None
            except Exception as exc:  # noqa: BLE001
                name, msg = None, f"Failed: {exc}"
            GLib.idle_add(lambda: (button.set_sensitive(True), self.update_account(msg)) and False)

        threading.Thread(target=work, daemon=True).start()

    def open_uri(self, url):
        GLib.idle_add(lambda: Gtk.UriLauncher.new(url).launch(self.win, None, None) and False)


class App(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        for name, cb, accels in (
            ("preferences", self.on_preferences, ["<Control>comma"]),
            ("about", self.on_about, []),
            ("quit", lambda *_: self.quit(), ["<Control>q", "<Control>w"]),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", cb)
            self.add_action(action)
            self.set_accels_for_action(f"app.{name}", accels)

    def do_startup(self):
        Adw.Application.do_startup(self)
        css = Gtk.CssProvider()
        css.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_activate(self):
        (self.props.active_window or Window(self)).present()

    def on_preferences(self, *_):
        Preferences(self.props.active_window).present(self.props.active_window)

    def on_about(self, *_):
        Adw.AboutDialog(
            application_name="postr", application_icon="document-send-symbolic", version=__version__,
            developer_name="Paul Mairo", license_type=Gtk.License.MIT_X11,
            comments="Write-only posting to X, Mastodon, Bluesky, LinkedIn and rmpr.xyz.",
        ).present(self.props.active_window)


def run():
    return App().run(None)
