"""LinkBoard - a tiny self-hosted page for your links, with thumbnails and groups."""
import html
import ipaddress
import io
import os
import re
import secrets
import shutil
import sqlite3
import tempfile
import zipfile
import sys
import threading
import time
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, Response, jsonify, redirect, request, send_from_directory, session
from flask.sessions import SecureCookieSessionInterface
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from PIL import Image
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DATA_DIR = os.environ.get("DATA_DIR", "/data")
THUMB_DIR = os.path.join(DATA_DIR, "thumbs")
DB_PATH = os.path.join(DATA_DIR, "linkboard.db")
os.makedirs(THUMB_DIR, exist_ok=True)

UA = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/130.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,image/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,nl;q=0.8,ar;q=0.6",
}
# Many sites (YouTube in the EU, Instagram, X, ...) answer a normal browser with a
# consent or login page, but give link-preview crawlers the real title and image.
BOT_UA = {
    "User-Agent": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "Accept": "text/html,application/xhtml+xml,image/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en",
}
OEMBED = [
    (re.compile(r"^https?://((www|m|music)\.)?youtube\.com/(watch|shorts/|live/|playlist)|^https?://youtu\.be/", re.I),
     "https://www.youtube.com/oembed"),
    (re.compile(r"^https?://(www\.)?vimeo\.com/", re.I), "https://vimeo.com/api/oembed.json"),
    (re.compile(r"^https?://(www\.|vm\.)?tiktok\.com/", re.I), "https://www.tiktok.com/oembed"),
]
COLORS = ["#4c8bf5", "#e5534b", "#e0a31b", "#3fa55a", "#d6589f", "#8e6ad8", "#2aa7b8", "#e8793a", "#7d8590"]

app = Flask(__name__, static_folder=None)
PAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # backups with many thumbnails can be large
if os.environ.get("BEHIND_PROXY", "").lower() in ("1", "true", "yes"):
    # Trust the reverse proxy's X-Forwarded-* headers: real visitor address (for the
    # wrong-password limit) and whether the visitor used https.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)


class _Sessions(SecureCookieSessionInterface):
    def get_cookie_secure(self, app):  # https visitors get an https-only cookie
        return request.is_secure


app.session_interface = _Sessions()
pool = ThreadPoolExecutor(max_workers=int(os.environ.get("FETCH_WORKERS", "4")))


# ---------------------------------------------------------------- database
def db():
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def init_db():
    with db() as c:
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript("""
        CREATE TABLE IF NOT EXISTS groups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            color TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            thumb TEXT NOT NULL DEFAULT '',
            thumb_kind TEXT NOT NULL DEFAULT '',
            group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            custom_title INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL
        );
        """)
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        cols = [r["name"] for r in c.execute("PRAGMA table_info(groups)")]
        if "position" not in cols:
            c.execute("ALTER TABLE groups ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
            c.execute("UPDATE groups SET position = id")
        if "position" not in [r["name"] for r in c.execute("PRAGMA table_info(links)")]:
            c.execute("ALTER TABLE links ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
            c.execute("UPDATE links SET position = -id")  # keeps the old look: newest first


def _is_local(hostish):
    """Bare LAN addresses (192.168.x.x, localhost, nas.local) default to http."""
    h = re.split(r"[/:?#]", hostish, maxsplit=1)[0].lower()
    try:
        return not ipaddress.ip_address(h).is_global
    except ValueError:
        return "." not in h or h.endswith((".local", ".lan", ".home", ".internal", ".home.arpa"))


def normalize_url(raw):
    raw = (raw or "").strip()
    if not raw or re.search(r"\s", raw):
        return None
    if "://" not in raw:
        if re.match(r"^(javascript|data|mailto|file|about|tel|chrome|edge|blob|vbscript):", raw, re.I):
            return None
        raw = ("http://" if _is_local(raw) else "https://") + raw
    try:
        p = urlparse(raw)
        p.port  # raises on a malformed port
    except ValueError:
        return None
    if p.scheme.lower() not in ("http", "https") or not p.hostname:
        return None
    if p.path == "/" and not p.query and not p.fragment:
        raw = raw.rstrip("/")
    return raw


def get_or_create_group(c, name):
    name = (name or "").strip()[:60]
    if not name:
        return None
    row = c.execute("SELECT id FROM groups WHERE name = ?", (name,)).fetchone()
    if row:
        return row["id"]
    n, last = c.execute("SELECT COUNT(*), COALESCE(MAX(position), 0) FROM groups").fetchone()
    return c.execute("INSERT INTO groups (name, color, position) VALUES (?, ?, ?)",
                     (name, COLORS[n % len(COLORS)], last + 1)).lastrowid


def add_link(c, url, group_id=None, title="", top=True):
    """Insert a link, first in the list (or last, for imports, so a file keeps its
    order). Returns the new id, or None if it already exists."""
    title = (title or "").strip()[:300]
    lo, hi = c.execute("SELECT COALESCE(MIN(position), 0), COALESCE(MAX(position), 0) FROM links").fetchone()
    try:
        return c.execute(
            "INSERT INTO links (url, title, group_id, custom_title, created_at, position) VALUES (?,?,?,?,?,?)",
            (url, title, group_id, 0, int(time.time()), lo - 1 if top else hi + 1)).lastrowid
    except sqlite3.IntegrityError:
        return None


# ------------------------------------------------------- metadata fetching
# Google/YouTube show EU visitors a "Before you continue" consent page instead of
# the real one. This cookie is what the "Reject all" button sets (no tracking).
CONSENT_HOSTS = ("youtube.com", "youtu.be", "google.com")
CONSENT_COOKIES = {"SOCS": "CAI", "CONSENT": "YES+cb"}


def _download(url, limit, headers=UA):
    host = (urlparse(url).hostname or "").lower()
    cookies = CONSENT_COOKIES if host.endswith(CONSENT_HOSTS) else None
    r = requests.get(url, headers=headers, cookies=cookies, timeout=12, stream=True)
    r.raise_for_status()
    if (urlparse(r.url).hostname or "").lower().startswith("consent."):
        r.close()
        raise RuntimeError("consent wall")
    data = r.raw.read(limit + 1, decode_content=True)
    ctype = r.headers.get("Content-Type", "").lower()
    final = r.url
    r.close()
    return data[:limit], ctype, final


def _save_thumb(link_id, data, kind):
    """Store image bytes as a small thumbnail. Returns the file name or None."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    name = f"{link_id}-{int(time.time())}"
    if kind == "image":
        if img.width < 80 or img.height < 60:
            return None
        img = img.convert("RGB")
        img.thumbnail((640, 640))
        name += ".webp"
        img.save(os.path.join(THUMB_DIR, name), "WEBP", quality=80)
    else:
        img = img.convert("RGBA")
        img.thumbnail((128, 128))
        name += ".png"
        img.save(os.path.join(THUMB_DIR, name), "PNG")
    return name


def _meta(soup, *keys):
    for key in keys:
        for attr in ("property", "name"):
            tag = soup.find("meta", attrs={attr: re.compile(f"^{re.escape(key)}$", re.I)})
            if tag and tag.get("content", "").strip():
                return tag["content"].strip()
    return ""


def _oembed(url):
    """Title and thumbnail from the site's official embed API, where one exists."""
    for rx, endpoint in OEMBED:
        if rx.search(url):
            try:
                r = requests.get(endpoint, params={"url": url, "format": "json"}, headers=UA, timeout=10)
                r.raise_for_status()
                d = r.json()
                return (d.get("title") or "").strip(), (d.get("thumbnail_url") or "").strip()
            except Exception:
                return "", ""
    return "", ""


def _scrape(url, headers):
    data, ctype, final = _download(url, 2_000_000, headers)
    out = {"title": "", "desc": "", "images": [], "icons": [], "final": final}
    if ctype.startswith("image/"):
        out["images"].append(final)
        return out
    soup = BeautifulSoup(data, "html.parser")
    out["title"] = _meta(soup, "og:title", "twitter:title") or (soup.title.get_text(strip=True) if soup.title else "")
    out["desc"] = _meta(soup, "og:description", "twitter:description", "description")
    for key in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"):
        v = _meta(soup, key)
        if v:
            out["images"].append(urljoin(final, v))
    for tag in soup.find_all("link", href=True):
        rel = " ".join(tag.get("rel") or []).lower()
        if "apple-touch-icon" in rel:
            out["icons"].insert(0, urljoin(final, tag["href"]))
        elif "icon" in rel:
            out["icons"].append(urljoin(final, tag["href"]))
    return out


def fetch_meta(link_id):
    with db() as c:
        row = c.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
    if not row:
        return
    url = row["url"]
    info = None
    for headers in (UA, BOT_UA):  # second try only when the first gave no picture
        try:
            cur = _scrape(url, headers)
        except Exception:
            continue
        if info is None or cur["images"]:
            if info and not cur["icons"]:
                cur["icons"] = info["icons"]
            info = cur
        if info["images"]:
            break
    o_title, o_image = _oembed(url)
    status = "ok" if (info or o_title or o_image) else "error"
    info = info or {"title": "", "desc": "", "images": [], "icons": [], "final": url}
    title, desc = o_title or info["title"], info["desc"]
    images = ([o_image] if o_image else []) + info["images"]
    icons = info["icons"] + [urljoin(info["final"], "/favicon.ico")]

    thumb, kind = None, ""
    for candidates, k in ((images, "image"), (icons, "icon")):
        for u in dict.fromkeys(candidates):
            try:
                img_data, _, _ = _download(u, 8_000_000)
            except Exception:
                continue
            thumb = _save_thumb(link_id, img_data, k)
            if thumb:
                kind = k
                break
        if thumb:
            break

    with db() as c:
        cur = c.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
        if not cur:
            if thumb:
                _remove_thumb(thumb)
            return
        new_title = cur["title"] if (cur["custom_title"] or (not title and cur["title"])) else title
        new_title = (new_title or urlparse(url).netloc)[:300]
        old = cur["thumb"]
        if not thumb:  # keep whatever we had before
            thumb, kind = cur["thumb"], cur["thumb_kind"]
        c.execute("UPDATE links SET title=?, description=?, thumb=?, thumb_kind=?, status=? WHERE id=?",
                  (new_title, desc[:500] or cur["description"], thumb, kind, status, link_id))
    if old and old != thumb:
        _remove_thumb(old)


def _remove_thumb(name):
    try:
        os.remove(os.path.join(THUMB_DIR, os.path.basename(name)))
    except OSError:
        pass


def queue(link_id):
    pool.submit(_safe_fetch, link_id)


def _safe_fetch(link_id):
    try:
        fetch_meta(link_id)
    except Exception:
        app.logger.exception("fetch failed for link %s", link_id)
        with db() as c:
            c.execute("UPDATE links SET status='error' WHERE id=? AND status='pending'", (link_id,))


# ------------------------------------------------------------------ import
TOKEN = re.compile(
    r"<h3[^>]*>(?P<folder>.*?)</h3>|(?P<open><dl\b[^>]*>)|(?P<close></dl>)|"
    r"<a\b[^>]*?href\s*=\s*[\"'](?P<href>[^\"']+)[\"'][^>]*>(?P<title>.*?)</a>",
    re.I | re.S)
ROOT_FOLDERS = {"favorites bar", "favourites bar", "bookmarks bar", "bookmarks toolbar",
                "bookmarks menu", "other favorites", "other bookmarks", "bookmarks", "favorites"}


def _text(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def parse_bookmarks_html(text):
    """Browser bookmark export (Edge/Chrome/Firefox). Yields (url, title, folder)."""
    stack, pending = [], None
    for m in TOKEN.finditer(text):
        if m.group("folder") is not None:
            pending = _text(m.group("folder"))
        elif m.group("open"):
            stack.append(pending)
            pending = None
        elif m.group("close"):
            if stack:
                stack.pop()
        else:
            named = [f for f in stack if f]
            folder = named[-1] if named else ""
            if folder.lower() in ROOT_FOLDERS and len(named) <= 1:
                folder = ""
            yield html.unescape(m.group("href")), _text(m.group("title")), folder


def parse_plain(text):
    """One link per line; anything that looks like a URL is picked up."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        found = re.findall(r"https?://[^\s<>\"']+", line)
        if found:
            for u in found:
                yield u.rstrip(".,;)"), "", ""
        elif re.match(r"^[\w.-]+\.[a-zA-Z]{2,}(/\S*)?$", line):
            yield line, "", ""


# ------------------------------------------------------------------- login
def get_setting(key, default=None):
    with db() as c:
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key, value):
    with db() as c:
        if value is None:
            c.execute("DELETE FROM settings WHERE key=?", (key,))
        else:
            c.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                      "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))


def auth_enabled():
    return bool(get_setting("auth_hash"))


def signed_in():
    """True when this browser holds a session made with the current credentials."""
    ver = get_setting("auth_ver")
    return bool(ver) and secrets.compare_digest(session.get("ver", ""), ver)


def _hash(password):
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


# Wrong-password throttle, per client address: 5 free tries, then a growing wait.
_fails, _fails_lock = {}, threading.Lock()


def _wait_seconds(ip):
    with _fails_lock:
        count, until = _fails.get(ip, (0, 0))
    return max(0, int(until - time.time()) + 1) if until > time.time() else 0


def _note_login(ip, ok):
    with _fails_lock:
        if ok:
            _fails.pop(ip, None)
            return
        count = _fails.get(ip, (0, 0))[0] + 1
        until = time.time() + min(300, 15 * 2 ** (count - 5)) if count >= 5 else 0
        _fails[ip] = (count, until)
        if len(_fails) > 5000:
            _fails.clear()


OPEN_ENDPOINTS = {"login_page", "api_login", "auth_status"}


@app.before_request
def require_login():
    if request.endpoint in OPEN_ENDPOINTS or not auth_enabled() or signed_in():
        return None
    if request.path.startswith("/api/"):
        return jsonify(error="Please sign in."), 401
    return redirect("/login")


@app.get("/login")
def login_page():
    if not auth_enabled() or signed_in():
        return redirect("/")
    return send_from_directory(PAGES, "login.html", max_age=0)


@app.get("/api/auth")
def auth_status():
    on = auth_enabled()
    inside = not on or signed_in()
    return jsonify(enabled=on, signed_in=inside, username=get_setting("auth_user", "") if inside else "")


@app.post("/api/login")
def api_login():
    d = request.get_json(force=True, silent=True) or {}
    ip = request.remote_addr or "?"
    wait = _wait_seconds(ip)
    if wait:
        return jsonify(error=f"Too many attempts. Try again in {wait} seconds."), 429
    user, pw_hash = get_setting("auth_user", ""), get_setting("auth_hash", "")
    ok = bool(pw_hash) and secrets.compare_digest(str(d.get("username", "")).strip().lower().encode(), user.lower().encode())
    ok = check_password_hash(pw_hash or _hash("x"), str(d.get("password", ""))) and ok
    _note_login(ip, ok)
    if not ok:
        return jsonify(error="Wrong username or password."), 401
    session.clear()
    session["ver"] = get_setting("auth_ver")
    session.permanent = bool(d.get("remember"))  # otherwise the cookie ends with the browser session
    return jsonify(ok=True)


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/auth")
def set_auth():
    """Turn the login on, or change it. Changing needs the current password."""
    d = request.get_json(force=True, silent=True) or {}
    user, pw = str(d.get("username", "")).strip(), str(d.get("password", ""))
    old = get_setting("auth_hash")
    if old and not check_password_hash(old, str(d.get("current_password", ""))):
        return jsonify(error="The current password is not correct."), 403
    if not user or len(user) > 60:
        return jsonify(error="Choose a username."), 400
    if len(pw) < 8:
        return jsonify(error="The password needs at least 8 characters."), 400
    ver = secrets.token_hex(16)  # new value signs every other device out
    set_setting("auth_user", user)
    set_setting("auth_hash", _hash(pw))
    set_setting("auth_ver", ver)
    session.clear()
    session["ver"] = ver
    session.permanent = True
    return jsonify(ok=True)


@app.delete("/api/auth")
def remove_auth():
    d = request.get_json(force=True, silent=True) or {}
    old = get_setting("auth_hash")
    if old and not check_password_hash(old, str(d.get("current_password", ""))):
        return jsonify(error="The current password is not correct."), 403
    for key in ("auth_user", "auth_hash", "auth_ver"):
        set_setting(key, None)
    session.clear()
    return jsonify(ok=True)


# --------------------------------------------------------------------- api
@app.get("/")
def index():
    return send_from_directory(PAGES, "index.html", max_age=0)


@app.get("/thumbs/<path:name>")
def thumbs(name):
    return send_from_directory(THUMB_DIR, name, max_age=31536000)


@app.get("/api/state")
def state():
    with db() as c:
        groups = [dict(r) for r in c.execute("SELECT * FROM groups ORDER BY position, id")]
        links = [dict(r) for r in c.execute("SELECT * FROM links ORDER BY position, id DESC")]
    return jsonify(groups=groups, links=links)


@app.post("/api/links")
def create_link():
    d = request.get_json(force=True, silent=True) or {}
    url = normalize_url(d.get("url"))
    if not url:
        return jsonify(error="That does not look like a web link."), 400
    with db() as c:
        link_id = add_link(c, url, d.get("group_id") or None)
    if link_id is None:
        return jsonify(error="This link is already saved."), 409
    queue(link_id)
    return jsonify(id=link_id), 201


def _ids(d):
    return list(dict.fromkeys(int(i) for i in d.get("ids", []) if str(i).isdigit()))


@app.post("/api/links/order")
def order_links():
    """Body: {"ids": [...]} - these links, in the order they should appear. They
    swap places among themselves only, so other links keep their position."""
    ids = _ids(request.get_json(force=True, silent=True) or {})
    with db() as c:
        rows = {r["id"]: r["position"] for r in
                c.execute(f"SELECT id, position FROM links WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
        ids = [i for i in ids if i in rows]
        slots = sorted(rows.values())
        if len(set(slots)) < len(slots):  # ties: spread them out below the smallest
            slots = list(range(slots[0], slots[0] + len(slots))) if slots else []
        for link_id, pos in zip(ids, slots):
            c.execute("UPDATE links SET position=? WHERE id=?", (pos, link_id))
    return jsonify(ok=True)


@app.post("/api/links/bulk")
def bulk_links():
    """Body: {"ids": [...], "group_id": 3 or null} to move, or {"ids": [...], "delete": true}."""
    d = request.get_json(force=True, silent=True) or {}
    ids = _ids(d)
    if not ids:
        return jsonify(error="Nothing selected."), 400
    marks = ",".join("?" * len(ids))
    thumbs = []
    with db() as c:
        if d.get("delete"):
            thumbs = [r["thumb"] for r in c.execute(f"SELECT thumb FROM links WHERE id IN ({marks})", ids) if r["thumb"]]
            c.execute(f"DELETE FROM links WHERE id IN ({marks})", ids)
        elif "group_id" in d:
            gid = d["group_id"] or None
            if gid is not None and not c.execute("SELECT 1 FROM groups WHERE id=?", (gid,)).fetchone():
                return jsonify(error="That group no longer exists."), 404
            c.execute(f"UPDATE links SET group_id=? WHERE id IN ({marks})", [gid] + ids)
        else:
            return jsonify(error="Nothing to do."), 400
    for name in thumbs:
        _remove_thumb(name)
    return jsonify(ok=True, count=len(ids))


@app.patch("/api/links/<int:link_id>")
def update_link(link_id):
    d = request.get_json(force=True, silent=True) or {}
    refetch = False
    with db() as c:
        row = c.execute("SELECT * FROM links WHERE id=?", (link_id,)).fetchone()
        if not row:
            return jsonify(error="Not found"), 404
        if "title" in d:
            t = (d["title"] or "").strip()[:300]
            if t != row["title"]:
                c.execute("UPDATE links SET title=?, custom_title=? WHERE id=?", (t, 1 if t else 0, link_id))
                refetch = refetch or not t
        if "group_id" in d:
            c.execute("UPDATE links SET group_id=? WHERE id=?", (d["group_id"] or None, link_id))
        if "url" in d:
            url = normalize_url(d["url"])
            if not url:
                return jsonify(error="That does not look like a web link."), 400
            if url != row["url"]:
                try:
                    c.execute("UPDATE links SET url=?, status='pending' WHERE id=?", (url, link_id))
                except sqlite3.IntegrityError:
                    return jsonify(error="This link is already saved."), 409
                refetch = True
    if refetch:
        queue(link_id)
    return jsonify(ok=True)


@app.post("/api/links/<int:link_id>/refresh")
def refresh_link(link_id):
    with db() as c:
        c.execute("UPDATE links SET status='pending' WHERE id=?", (link_id,))
    queue(link_id)
    return jsonify(ok=True)


@app.delete("/api/links/<int:link_id>")
def delete_link(link_id):
    with db() as c:
        row = c.execute("SELECT thumb FROM links WHERE id=?", (link_id,)).fetchone()
        c.execute("DELETE FROM links WHERE id=?", (link_id,))
    if row and row["thumb"]:
        _remove_thumb(row["thumb"])
    return jsonify(ok=True)


def _color(value):
    """Only plain #rrggbb colours are stored."""
    return isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value) is not None


@app.post("/api/groups")
def create_group():
    d = request.get_json(force=True, silent=True) or {}
    with db() as c:
        gid = get_or_create_group(c, d.get("name"))
        if gid is None:
            return jsonify(error="Give the group a name."), 400
        if _color(d.get("color")):
            c.execute("UPDATE groups SET color=? WHERE id=?", (d["color"], gid))
    return jsonify(id=gid), 201


@app.post("/api/groups/order")
def order_groups():
    """Body: {"ids": [3, 1, 2]} - the group ids in the order they should appear."""
    d = request.get_json(force=True, silent=True) or {}
    ids = [int(i) for i in d.get("ids", []) if str(i).isdigit()]
    with db() as c:
        known = [r["id"] for r in c.execute("SELECT id FROM groups ORDER BY position, id")]
        ordered = [i for i in dict.fromkeys(ids) if i in known] + [i for i in known if i not in ids]
        for pos, gid in enumerate(ordered, 1):
            c.execute("UPDATE groups SET position=? WHERE id=?", (pos, gid))
    return jsonify(ok=True)


@app.patch("/api/groups/<int:gid>")
def update_group(gid):
    d = request.get_json(force=True, silent=True) or {}
    with db() as c:
        try:
            if (d.get("name") or "").strip():
                c.execute("UPDATE groups SET name=? WHERE id=?", (d["name"].strip()[:60], gid))
            if _color(d.get("color")):
                c.execute("UPDATE groups SET color=? WHERE id=?", (d["color"], gid))
        except sqlite3.IntegrityError:
            return jsonify(error="A group with that name already exists."), 409
    return jsonify(ok=True)


@app.delete("/api/groups/<int:gid>")
def delete_group(gid):
    """Deletes the group; its links stay, ungrouped (or go too with ?links=1)."""
    with db() as c:
        if request.args.get("links") == "1":
            for r in c.execute("SELECT thumb FROM links WHERE group_id=?", (gid,)).fetchall():
                if r["thumb"]:
                    _remove_thumb(r["thumb"])
            c.execute("DELETE FROM links WHERE group_id=?", (gid,))
        c.execute("DELETE FROM groups WHERE id=?", (gid,))
    return jsonify(ok=True)


@app.post("/api/import")
def import_links():
    text = request.form.get("text", "")
    f = request.files.get("file")
    if f:
        text += "\n" + f.read().decode("utf-8", errors="replace")
    target = request.form.get("group_id") or None
    is_bookmarks = bool(re.search(r"<a\b[^>]*href", text, re.I))
    items = parse_bookmarks_html(text) if is_bookmarks else parse_plain(text)
    added, skipped, new_ids = 0, 0, []
    with db() as c:
        for raw, title, folder in items:
            url = normalize_url(raw)
            if not url:
                skipped += 1
                continue
            gid = target or (get_or_create_group(c, folder) if folder else None)
            link_id = add_link(c, url, gid, title, top=False)
            if link_id is None:
                skipped += 1
            else:
                added += 1
                new_ids.append(link_id)
    for link_id in new_ids:
        queue(link_id)
    return jsonify(added=added, skipped=skipped)


@app.get("/api/export")
def export_links():
    """Standard bookmarks file: re-importable here and in any browser."""
    e = html.escape
    out = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
           '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
           "<TITLE>Bookmarks</TITLE>", "<H1>Bookmarks</H1>", "<DL><p>"]
    with db() as c:
        groups = c.execute("SELECT * FROM groups ORDER BY position, id").fetchall()
        links = c.execute("SELECT * FROM links ORDER BY position, id DESC").fetchall()

    def rows(gid, pad):
        return [f'{pad}<DT><A HREF="{e(l["url"])}" ADD_DATE="{l["created_at"]}">{e(l["title"] or l["url"])}</A>'
                for l in links if l["group_id"] == gid]

    for g in groups:
        out += [f'    <DT><H3>{e(g["name"])}</H3>', "    <DL><p>", *rows(g["id"], "        "), "    </DL><p>"]
    out += rows(None, "    ") + ["</DL><p>", ""]
    return Response("\n".join(out), mimetype="text/html",
                    headers={"Content-Disposition": "attachment; filename=linkboard-bookmarks.html"})


# ------------------------------------------------------- backup and restore
# A backup is a zip holding the database and the thumbnails. With a password it is
# wrapped as: MAGIC + 16-byte salt + 12-byte nonce + AES-256-GCM(zip), key = scrypt(password).
MAGIC = b"LINKBOARD-BACKUP-1\n"
PRIVATE_SETTINGS = ("auth_user", "auth_hash", "auth_ver", "secret_key")  # never leave the server


def _key(password, salt):
    return Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(password.encode("utf-8"))


def make_backup(password=""):
    with tempfile.TemporaryDirectory() as tmp:
        snap = os.path.join(tmp, "linkboard.db")
        src, dst = sqlite3.connect(DB_PATH, timeout=30), sqlite3.connect(snap)
        with dst:
            src.backup(dst)  # consistent copy, even while the app is in use
        src.close()
        dst.execute(f"DELETE FROM settings WHERE key IN ({','.join('?' * len(PRIVATE_SETTINGS))})", PRIVATE_SETTINGS)
        dst.commit()
        dst.execute("VACUUM")
        dst.close()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, "linkboard.db")
            for name in sorted(os.listdir(THUMB_DIR)):
                z.write(os.path.join(THUMB_DIR, name), "thumbs/" + name, zipfile.ZIP_STORED)
    data = buf.getvalue()
    if password:
        salt, nonce = os.urandom(16), os.urandom(12)
        data = MAGIC + salt + nonce + AESGCM(_key(password, salt)).encrypt(nonce, data, MAGIC)
    return data


class RestoreError(Exception):
    pass


def restore_backup(data, password=""):
    if data.startswith(MAGIC):
        if not password:
            raise RestoreError("This backup is protected. Enter its password.")
        salt, nonce, body = data[len(MAGIC):len(MAGIC) + 16], data[len(MAGIC) + 16:len(MAGIC) + 28], data[len(MAGIC) + 28:]
        try:
            data = AESGCM(_key(password, salt)).decrypt(nonce, body, MAGIC)
        except InvalidTag:
            raise RestoreError("Wrong password, or the backup file is damaged.")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        z.getinfo("linkboard.db")
    except (zipfile.BadZipFile, KeyError):
        raise RestoreError("This is not a LinkBoard backup file.")
    with tempfile.TemporaryDirectory() as tmp:
        snap = os.path.join(tmp, "restore.db")
        with open(snap, "wb") as f:
            f.write(z.read("linkboard.db"))
        try:
            old = sqlite3.connect(snap)
            old.row_factory = sqlite3.Row
            groups = [dict(r) for r in old.execute("SELECT * FROM groups")]
            links = [dict(r) for r in old.execute("SELECT * FROM links")]
            old.close()
        except sqlite3.Error:
            raise RestoreError("The backup's database cannot be read.")
        new_thumbs = os.path.join(tmp, "thumbs")
        os.makedirs(new_thumbs)
        wanted = {l.get("thumb") for l in links if l.get("thumb")}
        for info in z.infolist():
            name = os.path.basename(info.filename)
            if info.filename.startswith("thumbs/") and name in wanted and re.fullmatch(r"[\w.-]+\.(webp|png)", name):
                with open(os.path.join(new_thumbs, name), "wb") as f:
                    f.write(z.read(info))
        with db() as c:  # one transaction: either everything is replaced or nothing
            g_cols = [r["name"] for r in c.execute("PRAGMA table_info(groups)")]
            l_cols = [r["name"] for r in c.execute("PRAGMA table_info(links)")]
            c.execute("DELETE FROM links")
            c.execute("DELETE FROM groups")
            for table, cols, rows in (("groups", g_cols, groups), ("links", l_cols, links)):
                for row in rows:
                    row.setdefault("position", row["id"] if table == "groups" else -row["id"])
                    use = [k for k in cols if k in row]
                    c.execute(f"INSERT INTO {table} ({','.join(use)}) VALUES ({','.join('?' * len(use))})", [row[k] for k in use])
            c.execute("UPDATE links SET status='error' WHERE status='pending'")
        for name in os.listdir(THUMB_DIR):
            _remove_thumb(name)
        for name in os.listdir(new_thumbs):
            shutil.move(os.path.join(new_thumbs, name), os.path.join(THUMB_DIR, name))
    return len(links), len(groups)


@app.post("/api/backup")
def api_backup():
    d = request.get_json(force=True, silent=True) or {}
    password = str(d.get("password", ""))
    data = make_backup(password)
    name = "linkboard-backup-" + time.strftime("%Y-%m-%d") + (".lbk" if password else ".zip")
    return Response(data, mimetype="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={name}", "X-Filename": name})


@app.post("/api/restore")
def api_restore():
    f = request.files.get("file")
    if not f:
        return jsonify(error="Choose a backup file."), 400
    try:
        links, groups = restore_backup(f.read(), request.form.get("password", ""))
    except RestoreError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True, links=links, groups=groups)


init_db()
if not get_setting("secret_key"):
    set_setting("secret_key", secrets.token_hex(32))
app.secret_key = get_setting("secret_key")
app.config.update(SESSION_COOKIE_NAME="linkboard", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  PERMANENT_SESSION_LIFETIME=timedelta(days=30))
with db() as _c:  # pick up anything interrupted by a restart
    for _r in _c.execute("SELECT id FROM links WHERE status='pending'").fetchall():
        queue(_r["id"])

if __name__ == "__main__":
    if sys.argv[1:] == ["reset-login"]:  # docker exec linkboard python app.py reset-login
        for _key in ("auth_user", "auth_hash", "auth_ver"):
            set_setting(_key, None)
        print("Login removed. LinkBoard is open again; set a new login in Settings.")
        sys.exit(0)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
