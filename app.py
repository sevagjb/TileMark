"""TileMark - a tiny self-hosted page for your links, with thumbnails and groups."""
import html
import ipaddress
import hashlib
import io
import json
import os
import re
import secrets
import shutil
import socket
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
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool
from bs4 import BeautifulSoup
from flask import Flask, Response, g, jsonify, redirect, request, send_from_directory, session
from flask.sessions import SecureCookieSessionInterface
from werkzeug.security import check_password_hash, generate_password_hash
from PIL import Image
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

DATA_DIR = os.environ.get("DATA_DIR", "/data")
THUMB_DIR = os.path.join(DATA_DIR, "thumbs")
DB_PATH = os.path.join(DATA_DIR, "tilemark.db")
os.makedirs(THUMB_DIR, exist_ok=True)
Image.MAX_IMAGE_PIXELS = 50_000_000  # refuse "decompression bomb" pictures early

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
SCHEMA = 2  # 1 = TileMark 1.0 (one owner), 2 = several users

app = Flask(__name__, static_folder=None)
PAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages")
app.config["MAX_CONTENT_LENGTH"] = 1024 * 1024 * 1024  # backups with many thumbnails can be large
class _Sessions(SecureCookieSessionInterface):
    def get_cookie_secure(self, app):
        # https visitors get an https-only cookie, whether they reach the app directly
        # or through a reverse proxy (which reports the scheme in X-Forwarded-Proto).
        # A forged header only changes the forger's own cookie, so it needs no setting.
        return request.is_secure or request.headers.get("X-Forwarded-Proto", "").split(",")[-1].strip() == "https"


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
        c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        schema = c.execute("SELECT value FROM settings WHERE key='schema'").fetchone()
    if not (schema and int(schema["value"]) >= SCHEMA):
        _upgrade_v1()
        _migrate_v2()
    with db() as c:  # columns added after 1.1.0
        if "ha_user" not in [r["name"] for r in c.execute("PRAGMA table_info(users)")]:
            c.execute("ALTER TABLE users ADD COLUMN ha_user TEXT NOT NULL DEFAULT ''")


def _upgrade_v1():
    """The 1.0 tables and every column 1.0 added over time (a no-op on a current 1.0 database)."""
    with db() as c:
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
        cols = [r["name"] for r in c.execute("PRAGMA table_info(groups)")]
        if "position" not in cols:
            c.execute("ALTER TABLE groups ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
            c.execute("UPDATE groups SET position = id")
        if "position" not in [r["name"] for r in c.execute("PRAGMA table_info(links)")]:
            c.execute("ALTER TABLE links ADD COLUMN position INTEGER NOT NULL DEFAULT 0")
            c.execute("UPDATE links SET position = -id")  # keeps the old look: newest first
        have = [r["name"] for r in c.execute("PRAGMA table_info(links)")]
        for col, ddl in (("pinned", "INTEGER NOT NULL DEFAULT 0"), ("note", "TEXT NOT NULL DEFAULT ''"),
                         ("opened_at", "INTEGER NOT NULL DEFAULT 0"), ("custom_thumb", "INTEGER NOT NULL DEFAULT 0"),
                         ("broken", "INTEGER NOT NULL DEFAULT 0"), ("checked_at", "INTEGER NOT NULL DEFAULT 0")):
            if col not in have:
                c.execute(f"ALTER TABLE links ADD COLUMN {col} {ddl}")


LINK_COLS = ("id", "url", "title", "description", "thumb", "thumb_kind", "group_id", "status", "custom_title",
             "created_at", "position", "pinned", "note", "opened_at", "custom_thumb", "broken", "checked_at")
LEGACY_KEYS = ("auth_user", "auth_hash", "auth_ver", "api_key_hash")


def _migrate_v2():
    """Give links and groups an owner. SQLite cannot change a UNIQUE constraint in
    place, so both tables are rebuilt, inside one transaction: a failure leaves the
    1.0 database exactly as it was. The 1.0 login (if any) becomes the first admin
    and owns everything; without one, the rows wait for the first account."""
    con = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = OFF")  # only effective outside a transaction
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT value FROM settings WHERE key='schema'").fetchone()
        if row and int(row["value"]) >= SCHEMA:  # another process got here first
            con.execute("ROLLBACK")
            return
        for stmt in (
            """CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                pw_hash TEXT NOT NULL,
                is_admin INTEGER NOT NULL DEFAULT 0,
                ver TEXT NOT NULL,
                api_key_hash TEXT NOT NULL DEFAULT '',
                created_at INTEGER NOT NULL)""",
            """CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                PRIMARY KEY (user_id, key))""",
            """CREATE TABLE groups_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL COLLATE NOCASE,
                color TEXT NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                UNIQUE (user_id, name))""",
            """CREATE TABLE links_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                url TEXT NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                description TEXT NOT NULL DEFAULT '',
                thumb TEXT NOT NULL DEFAULT '',
                thumb_kind TEXT NOT NULL DEFAULT '',
                group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                custom_title INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL,
                position INTEGER NOT NULL DEFAULT 0,
                pinned INTEGER NOT NULL DEFAULT 0,
                note TEXT NOT NULL DEFAULT '',
                opened_at INTEGER NOT NULL DEFAULT 0,
                custom_thumb INTEGER NOT NULL DEFAULT 0,
                broken INTEGER NOT NULL DEFAULT 0,
                checked_at INTEGER NOT NULL DEFAULT 0,
                UNIQUE (user_id, url))""",
        ):
            con.execute(stmt)
        legacy = {r["key"]: r["value"] for r in
                  con.execute(f"SELECT key, value FROM settings WHERE key IN ({','.join('?' * len(LEGACY_KEYS))})", LEGACY_KEYS)}
        owner = None
        if legacy.get("auth_hash"):
            owner = con.execute(
                "INSERT INTO users (username, pw_hash, is_admin, ver, api_key_hash, created_at) VALUES (?,?,1,?,?,?)",
                ((legacy.get("auth_user") or "admin")[:60], legacy["auth_hash"], secrets.token_hex(16),
                 legacy.get("api_key_hash", ""), int(time.time()))).lastrowid
        con.execute("INSERT INTO groups_v2 (id, user_id, name, color, position) "
                    "SELECT id, ?, name, color, position FROM groups", (owner,))
        cols = ",".join(LINK_COLS)
        con.execute(f"INSERT INTO links_v2 (user_id, {cols}) SELECT ?, {cols} FROM links", (owner,))
        for stmt in ("DROP TABLE links", "DROP TABLE groups",
                     "ALTER TABLE groups_v2 RENAME TO groups", "ALTER TABLE links_v2 RENAME TO links",
                     "CREATE INDEX IF NOT EXISTS links_user ON links(user_id, position)",
                     "CREATE INDEX IF NOT EXISTS groups_user ON groups(user_id, position)"):
            con.execute(stmt)
        con.execute(f"DELETE FROM settings WHERE key IN ({','.join('?' * len(LEGACY_KEYS))})", LEGACY_KEYS)
        con.execute("INSERT INTO settings (key, value) VALUES ('schema', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(SCHEMA),))
        bad = con.execute("PRAGMA foreign_key_check").fetchall()
        if bad:
            raise RuntimeError(f"database check failed after upgrade: {[tuple(b) for b in bad][:5]}")
        con.execute("COMMIT")
    except BaseException:
        if con.in_transaction:
            con.execute("ROLLBACK")
        raise
    finally:
        con.close()


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


def own_group(c, uid, gid):
    """The group id if it exists and belongs to this user, else None."""
    try:
        gid = int(gid)
    except (TypeError, ValueError):
        return None
    return gid if c.execute("SELECT 1 FROM groups WHERE id=? AND user_id=?", (gid, uid)).fetchone() else None


def get_or_create_group(c, uid, name):
    name = (name or "").strip()[:60]
    if not name:
        return None
    row = c.execute("SELECT id FROM groups WHERE user_id=? AND name=?", (uid, name)).fetchone()
    if row:
        return row["id"]
    n, last = c.execute("SELECT COUNT(*), COALESCE(MAX(position), 0) FROM groups WHERE user_id=?", (uid,)).fetchone()
    return c.execute("INSERT INTO groups (user_id, name, color, position) VALUES (?, ?, ?, ?)",
                     (uid, name, COLORS[n % len(COLORS)], last + 1)).lastrowid


def add_link(c, uid, url, group_id=None, title="", top=True):
    """Insert a link, first in the list (or last, for imports, so a file keeps its
    order). Returns the new id, or None if this user already has it."""
    title = (title or "").strip()[:300]
    lo, hi = c.execute("SELECT COALESCE(MIN(position), 0), COALESCE(MAX(position), 0) FROM links WHERE user_id=?",
                       (uid,)).fetchone()
    try:
        return c.execute(
            "INSERT INTO links (user_id, url, title, group_id, custom_title, created_at, position) VALUES (?,?,?,?,?,?,?)",
            (uid, url, title, group_id, 0, int(time.time()), lo - 1 if top else hi + 1)).lastrowid
    except sqlite3.IntegrityError:
        return None


# ------------------------------------------------------- safe outgoing fetch
# Every request the server makes on behalf of a link (page, picture, link check)
# goes through safe_get. Links and their og:image addresses come from pages anyone
# can write, so without this a page could point TileMark at http://homeassistant
# .local:8123/... or a cloud metadata address and have the answer stored as a
# thumbnail. Rules:
#  - loopback, link-local (incl. 169.254.169.254), multicast and reserved
#    addresses are never fetched;
#  - private LAN addresses only when the admin turns on "fetch_private";
#  - redirects are followed one hop at a time and every hop is checked again;
#  - the address actually connected to is checked as well, so a name that
#    resolves differently a second time (DNS rebinding) is caught too.
class Blocked(Exception):
    """The address is not one TileMark is allowed to fetch."""


_guard = threading.local()
_NET0 = ipaddress.ip_network("0.0.0.0/8")


def _addr_allowed(addr, allow_private):
    try:
        a = ipaddress.ip_address(str(addr).split("%")[0])
    except ValueError:
        return False
    if a.version == 6 and a.ipv4_mapped:
        a = a.ipv4_mapped
    if a.is_loopback or a.is_link_local or a.is_multicast or a.is_unspecified or a.is_reserved:
        return False
    if a.version == 4 and a in _NET0:
        return False
    return a.is_global or bool(allow_private)


def _host_allowed(host, port, allow_private):
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise requests.ConnectionError(f"Cannot find {host}")
    return bool(infos) and all(_addr_allowed(i[4][0], allow_private) for i in infos)


class _PeerCheck:
    def _new_conn(self):
        sock = super()._new_conn()
        try:
            peer = sock.getpeername()[0]
        except OSError:
            peer = ""
        if not _addr_allowed(peer, getattr(_guard, "allow_private", False)):
            sock.close()
            raise Blocked(f"Connecting to {peer} is not allowed")
        return sock


class _GuardHTTPConnection(_PeerCheck, HTTPConnection):
    pass


class _GuardHTTPSConnection(_PeerCheck, HTTPSConnection):
    pass


class _GuardHTTPPool(HTTPConnectionPool):
    ConnectionCls = _GuardHTTPConnection


class _GuardHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _GuardHTTPSConnection


class _GuardAdapter(HTTPAdapter):
    """Direct connections get the peer check. (Through a configured HTTP proxy the
    peer is the proxy itself; there the per-hop name check still applies.)"""
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {"http": _GuardHTTPPool, "https": _GuardHTTPSPool}


# Google/YouTube show EU visitors a "Before you continue" consent page instead of
# the real one. This cookie is what the "Reject all" button sets (no tracking).
CONSENT_HOSTS = ("youtube.com", "youtu.be", "google.com")
CONSENT_COOKIES = {"SOCS": "CAI", "CONSENT": "YES+cb"}
MAX_REDIRECTS = 5


def fetch_private():
    return get_setting("fetch_private", "off") == "on"


def safe_get(url, headers=UA, timeout=12, params=None):
    """Like requests.get(url, stream=True), with the rules above. The caller closes
    the response. Raises Blocked for a refused address."""
    allow = fetch_private()
    _guard.allow_private = allow
    s = requests.Session()
    s.mount("http://", _GuardAdapter())
    s.mount("https://", _GuardAdapter())
    for _ in range(MAX_REDIRECTS + 1):
        p = urlparse(url)
        try:
            port = p.port or (443 if p.scheme == "https" else 80)
        except ValueError:
            raise Blocked("Not a valid address")
        if p.scheme not in ("http", "https") or not p.hostname:
            raise Blocked("Not a web address")
        if not _host_allowed(p.hostname, port, allow):
            raise Blocked(f"{p.hostname} is a local or reserved address")
        host = p.hostname.lower()
        r = s.get(url, headers=headers, params=params, timeout=timeout, stream=True, allow_redirects=False,
                  cookies=CONSENT_COOKIES if host.endswith(CONSENT_HOSTS) else None)
        params = None
        if r.is_redirect:
            url = urljoin(r.url, r.headers["Location"])
            r.close()
            continue
        return r
    raise requests.TooManyRedirects("Too many redirects")


# ------------------------------------------------------- metadata fetching
def _download(url, limit, headers=UA):
    r = safe_get(url, headers)
    try:
        r.raise_for_status()
        if (urlparse(r.url).hostname or "").lower().startswith("consent."):
            raise RuntimeError("consent wall")
        data = r.raw.read(limit + 1, decode_content=True)
        return data[:limit], r.headers.get("Content-Type", "").lower(), r.url
    finally:
        r.close()


def _save_thumb(link_id, data, kind):
    """Store image bytes as a small thumbnail. Returns the file name or None."""
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except Exception:
        return None
    name = f"{link_id}-{int(time.time() * 1000)}-{secrets.token_hex(3)}"
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
                r = safe_get(endpoint, UA, timeout=10, params={"url": url, "format": "json"})
                try:
                    r.raise_for_status()
                    d = json.loads(r.raw.read(1_000_000, decode_content=True))
                finally:
                    r.close()
                return (d.get("title") or "").strip(), (d.get("thumbnail_url") or "").strip()
            except Exception:
                return "", ""
    return "", ""


# Bot-protection and consent screens ("Just a moment...", "Security Check") answer
# with their own title instead of the page's. Saving that would replace a real
# title with a meaningless one, so such pages count as "no information": the
# previous title is kept, or the site name is used.
WALL_TITLE = re.compile(
    r"^\s*(just a moment|one moment,? please|please wait|attention required|security check|"
    r"checking (your|if the site connection is secure|your browser)|verify(ing)? you are (a )?human|"
    r"are you a (robot|human)|access denied|ddos[- ]guard|bot verification|human verification|"
    r"captcha|redirecting|request blocked|before you continue|too many requests)\b[\s.!…|:-]*"
    r"(\|\s*cloudflare)?[\s.!…]*$", re.I)


def is_wall_title(title):
    return bool(title) and bool(WALL_TITLE.match(title))


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
    if is_wall_title(out["title"]):  # the wall's own picture and text say nothing about the page
        out.update(title="", desc="", images=[])
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
        except Blocked:
            break  # a local address: the second try would be refused the same way
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
    own = row["custom_thumb"]  # the user's own picture is never replaced by a fetched one
    for candidates, k in (() if own else ((images, "image"), (icons, "icon"))):
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
        keep_old = cur["title"] and not is_wall_title(cur["title"])
        new_title = cur["title"] if (cur["custom_title"] or (not title and keep_old)) else title
        new_title = (new_title or urlparse(url).netloc)[:300]
        old = cur["thumb"]
        if not thumb:  # keep whatever we had before
            thumb, kind = cur["thumb"], cur["thumb_kind"]
        if cur["custom_thumb"]:
            if thumb and thumb != cur["thumb"]:
                _remove_thumb(thumb)
            thumb, kind = cur["thumb"], cur["thumb_kind"]
        c.execute("UPDATE links SET title=?, description=?, thumb=?, thumb_kind=?, status=? WHERE id=?",
                  (new_title, desc[:500] or cur["description"], thumb, kind, status, link_id))
        if status == "ok":
            c.execute("UPDATE links SET broken=0, checked_at=? WHERE id=?", (int(time.time()), link_id))
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


# -------------------------------------------------------------- link check
# Marks links that no longer work. "Broken" means: the address could not be reached
# on two tries, or the site answered "not found" (404) or "gone" (410). Login walls,
# bot blocks, server errors and addresses TileMark may not fetch are NOT counted,
# to avoid false alarms.
_check = {"running": False, "done": 0, "total": 0, "uid": None}
_check_lock = threading.Lock()
CHECK_EVERY = 7 * 24 * 3600


def _probe(url):
    try:
        r = safe_get(url, UA, timeout=15)
        code = r.status_code
        r.close()
    except Blocked:
        return "unknown"
    except requests.exceptions.RequestException:
        return "broken"
    return "broken" if code in (404, 410) else "ok" if code < 400 else "unknown"


def _check_one(link_id, url):
    result = _probe(url)
    if result == "broken":
        time.sleep(8)
        result = _probe(url)
    with db() as c:
        if result == "unknown":
            c.execute("UPDATE links SET checked_at=? WHERE id=?", (int(time.time()), link_id))
        else:
            c.execute("UPDATE links SET broken=?, checked_at=? WHERE id=?",
                      (1 if result == "broken" else 0, int(time.time()), link_id))
    with _check_lock:
        _check["done"] += 1


def run_link_check(uid=None):
    """Check links in the background: one user's (the "Check now" button) or everyone's
    (the weekly run, uid None). False if a check is already running."""
    with _check_lock:
        if _check["running"]:
            return False
        _check.update(running=True, done=0, total=0, uid=uid)

    def work():
        try:
            with db() as c:
                rows = c.execute("SELECT id, url FROM links" + (" WHERE user_id=?" if uid else ""),
                                 (uid,) if uid else ()).fetchall()
            with _check_lock:
                _check["total"] = len(rows)
            with ThreadPoolExecutor(max_workers=4) as ex:
                for r in rows:
                    ex.submit(_check_one, r["id"], r["url"])
            now = str(int(time.time()))
            if uid:
                set_user_setting(uid, "linkcheck_last", now)
            else:
                set_setting("linkcheck_last", now)
        except Exception:
            app.logger.exception("link check failed")
        finally:
            with _check_lock:
                _check["running"] = False

    threading.Thread(target=work, daemon=True).start()
    return True


def _check_scheduler():
    time.sleep(120)
    while True:
        try:
            if get_setting("linkcheck", "on") == "on" and time.time() - int(get_setting("linkcheck_last", "0")) > CHECK_EVERY:
                run_link_check()
        except Exception:
            app.logger.exception("link check scheduler")
        try:
            if daily_backup_on() and time.time() - int(get_setting("backup_last", "0")) > BACKUP_EVERY:
                daily_backup()
        except Exception:
            app.logger.exception("daily backup failed")
        time.sleep(1800)


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


# ---------------------------------------------------------------- settings
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


def get_user_setting(uid, key, default=None):
    with db() as c:
        row = c.execute("SELECT value FROM user_settings WHERE user_id=? AND key=?", (uid, key)).fetchone()
    return row["value"] if row else default


def set_user_setting(uid, key, value):
    with db() as c:
        c.execute("INSERT INTO user_settings (user_id, key, value) VALUES (?, ?, ?) "
                  "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value", (uid, key, value))


# ------------------------------------------------------------------- login
def _hash(password):
    return generate_password_hash(password, method="pbkdf2:sha256:600000")


_DUMMY_HASH = _hash(secrets.token_hex(8))  # so a wrong username takes as long as a wrong password


def setup_needed():
    with db() as c:
        return c.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None


# The welcome screen of a new installation asks for this one-time code, which is
# only printed in the container log. Without it, whoever reaches a fresh install
# first (someone else on the network, or anyone if it is exposed) could create the
# admin account. It is removed as soon as the first account exists.
SETUP_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I


def setup_code():
    code = get_setting("setup_code")
    if not code:
        code = "-".join("".join(secrets.choice(SETUP_ALPHABET) for _ in range(4)) for _ in range(3))
        set_setting("setup_code", code)
    return code


def _same_code(sent, code):
    norm = lambda s: re.sub(r"[^A-Z0-9]", "", str(s).upper())
    return secrets.compare_digest(norm(sent).encode(), norm(code).encode())


def print_setup_code():
    line = "=" * 64
    print(f"\n{line}\n  TileMark has no account yet.\n  Open it in your browser and enter this setup code:\n\n"
          f"      {setup_code()}\n\n  (Show it again: docker exec tilemark python app.py setup-code)\n{line}\n", flush=True)


# ------------------------------------------------- Home Assistant add-on
# As an add-on (TILEMARK_HA_ADDON=1, set by the add-on's config.yaml) TileMark
# also opens in the Home Assistant sidebar through "ingress". There, Home Assistant
# has already signed the person in and tells the add-on who it is in X-Remote-User-*
# headers; the Supervisor removes any copies a browser tries to send. Those headers
# are believed only in add-on mode and only from the Supervisor's own address, so a
# request on the direct port can never use them. Every HA user gets their own
# TileMark account on first visit: the first one, and HA admins, become admins.
HA_ADDON = os.environ.get("TILEMARK_HA_ADDON") == "1"
HA_PROXY = "172.30.32.2"
HA_ADMIN_GROUP = "system-admin"


def via_ingress():
    return HA_ADDON and request.remote_addr == HA_PROXY and bool(request.headers.get("X-Remote-User-Id", "").strip())


def base_path():
    """The path prefix the browser sees: /api/hassio_ingress/<token> through ingress, else ''."""
    if HA_ADDON and request.remote_addr == HA_PROXY:
        p = request.headers.get("X-Ingress-Path", "")
        if re.fullmatch(r"/api/hassio_ingress/[\w-]+", p):
            return p
    return ""


def ingress_user():
    hid = request.headers.get("X-Remote-User-Id", "").strip()[:64]
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE ha_user=?", (hid,)).fetchone()
    if row:
        return row
    name = (request.headers.get("X-Remote-User-Name") or request.headers.get("X-Remote-User-Display-Name") or "user")
    name = re.sub(r"\s+", " ", name).strip()[:50] or "user"
    ha_admin = HA_ADMIN_GROUP in request.headers.get("X-Remote-User-Groups", "").split(",")
    con = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute("SELECT * FROM users WHERE ha_user=?", (hid,)).fetchone()
        if not row:
            first = con.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None
            username, n = name, 1
            while con.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                n += 1
                username = f"{name}-{n}"
            uid = con.execute(
                "INSERT INTO users (username, pw_hash, is_admin, ver, created_at, ha_user) VALUES (?,?,?,?,?,?)",
                (username, _hash(secrets.token_urlsafe(24)), 1 if (first or ha_admin) else 0, secrets.token_hex(16),
                 int(time.time()), hid)).lastrowid
            if first:  # same as the welcome screen: existing links become this account's
                con.execute("UPDATE groups SET user_id=? WHERE user_id IS NULL", (uid,))
                con.execute("UPDATE links SET user_id=? WHERE user_id IS NULL", (uid,))
                con.execute("DELETE FROM settings WHERE key='setup_code'")
            row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        con.execute("COMMIT")
    finally:
        if con.in_transaction:
            con.execute("ROLLBACK")
        con.close()
    return row


def current_user():
    """The signed-in user's row: through Home Assistant ingress, or because this
    browser holds a session made with the user's current password (changing it
    signs every other device out)."""
    if via_ingress():
        return ingress_user()
    uid = session.get("uid")
    if not uid:
        return None
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if row and secrets.compare_digest(str(session.get("ver", "")), row["ver"]):
        return row
    return None


def key_user():
    """The user whose API key this request carries ("Authorization: Bearer <key>")."""
    sent = request.headers.get("Authorization", "")
    if not sent.startswith("Bearer ") or not sent[7:].strip():
        return None
    digest = hashlib.sha256(sent[7:].strip().encode()).hexdigest()
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE api_key_hash=?", (digest,)).fetchone()
    return row if row and secrets.compare_digest(row["api_key_hash"], digest) else None


def me():
    return g.user["id"]


def _sign_in(user):
    session.clear()
    session["uid"] = user["id"]
    session["ver"] = user["ver"]


# Wrong-password throttle. It works the same with or without a reverse proxy, so no
# setting is needed:
#  - per visitor: 5 free tries, then a growing wait. Behind a proxy the visitor is the
#    last X-Forwarded-For entry (the one the proxy itself adds), otherwise the peer.
#  - per connecting address: at most 20 wrong tries a minute. This caps anyone who
#    connects directly and invents X-Forwarded-For values to look like many visitors.
_fails, _peer_fails, _fails_lock = {}, {}, threading.Lock()
PEER_LIMIT, PEER_WINDOW = 20, 60


def _client():
    peer = request.remote_addr or "?"
    fwd = request.headers.get("X-Forwarded-For", "").split(",")[-1].strip()
    return peer, f"{peer}|{fwd}" if fwd else peer


def _wait_seconds(client):
    peer, visitor = client
    now = time.time()
    with _fails_lock:
        until = _fails.get(visitor, (0, 0))[1]
        recent = [t for t in _peer_fails.get(peer, []) if now - t < PEER_WINDOW]
        _peer_fails[peer] = recent
    wait = int(until - now) + 1 if until > now else 0
    if len(recent) >= PEER_LIMIT:
        wait = max(wait, int(recent[0] + PEER_WINDOW - now) + 1)
    return wait


def _note_login(client, ok):
    peer, visitor = client
    with _fails_lock:
        if ok:
            _fails.pop(visitor, None)
            return
        count = _fails.get(visitor, (0, 0))[0] + 1
        until = time.time() + min(300, 15 * 2 ** (count - 5)) if count >= 5 else 0
        _fails[visitor] = (count, until)
        _peer_fails.setdefault(peer, []).append(time.time())
        if len(_fails) > 5000:
            _fails.clear()
        if len(_peer_fails) > 5000:
            _peer_fails.clear()


def _check_new_credentials(username, password, need_password=True):
    if not username or len(username) > 60:
        return "Choose a username (at most 60 characters)."
    if need_password and len(password) < 8:
        return "The password needs at least 8 characters."
    return None


OPEN_ENDPOINTS = {"login_page", "api_login", "auth_status", "api_setup", "icon", "save_page", "manifest",
                  "service_worker", "healthz"}
KEY_ENDPOINTS = {"create_link", "list_groups"}  # all an API key may do: add links, read group names
ADMIN_ENDPOINTS = {"list_users", "create_user", "update_user", "delete_user", "save_settings"}


@app.before_request
def require_login():
    g.user = current_user()
    if request.endpoint in OPEN_ENDPOINTS:
        return None
    if g.user is None and request.endpoint in KEY_ENDPOINTS:
        g.user = key_user()
    if g.user is None:
        if request.path.startswith("/api/"):
            return jsonify(error="Please sign in.", setup=setup_needed()), 401
        return redirect(base_path() + "/login")
    if request.endpoint in ADMIN_ENDPOINTS and not g.user["is_admin"]:
        return jsonify(error="Only an admin can do this."), 403
    return None


@app.get("/healthz")
def healthz():
    """For the Docker health check and the Home Assistant watchdog: the app answers
    and its database can be read. Says nothing else."""
    try:
        with db() as c:
            c.execute("SELECT 1 FROM settings LIMIT 1").fetchone()
    except sqlite3.Error:
        return Response("database unavailable\n", status=503, mimetype="text/plain")
    return Response("ok\n", mimetype="text/plain")


@app.get("/login")
def login_page():
    if current_user():
        nxt = request.args.get("next", "")
        return redirect(base_path() + (nxt if nxt.startswith("/save") else "/"))
    return send_from_directory(PAGES, "login.html", max_age=0)


@app.get("/save")
def save_page():
    """The small "Save to TileMark" window (browser button, phone share). The page
    itself holds nothing private; saving still needs a sign-in."""
    return send_from_directory(PAGES, "save.html", max_age=0)


@app.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(PAGES, "manifest.webmanifest", mimetype="application/manifest+json", max_age=0)


@app.get("/sw.js")
def service_worker():
    return send_from_directory(PAGES, "sw.js", mimetype="text/javascript", max_age=0)


@app.get("/icon-<name>.png")
def icon(name):
    if not re.fullmatch(r"[a-z0-9-]+", name):
        return jsonify(error="Not found"), 404
    return send_from_directory(PAGES, f"icon-{name}.png", max_age=86400)


@app.get("/api/auth")
def auth_status():
    u = g.user
    return jsonify(signed_in=bool(u), setup=not u and setup_needed(),
                   username=u["username"] if u else "", is_admin=bool(u and u["is_admin"]),
                   has_key=bool(u and u["api_key_hash"]), ha=bool(u) and via_ingress(), addon=HA_ADDON)


@app.post("/api/setup")
def api_setup():
    """Create the first account (an admin). Only possible while there is no account;
    links saved before (an open 1.0 installation) become this account's."""
    d = request.get_json(force=True, silent=True) or {}
    user, pw = str(d.get("username", "")).strip(), str(d.get("password", ""))
    problem = _check_new_credentials(user, pw)
    if problem:
        return jsonify(error=problem), 400
    if not setup_needed():
        return jsonify(error="TileMark is already set up. Sign in instead."), 409
    ip = _client()
    wait = _wait_seconds(ip)
    if wait:
        return jsonify(error=f"Too many attempts. Try again in {wait} seconds."), 429
    ok = _same_code(d.get("code", ""), setup_code())
    _note_login(ip, ok)
    if not ok:
        return jsonify(error="That setup code is not right. It is shown in the container log "
                             "(docker logs tilemark, or the log in Dockge).", code=True), 403
    con = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    con.row_factory = sqlite3.Row
    try:
        con.execute("BEGIN IMMEDIATE")  # two browsers racing: only one wins
        if con.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            con.execute("ROLLBACK")
            return jsonify(error="TileMark is already set up. Sign in instead."), 409
        uid = con.execute("INSERT INTO users (username, pw_hash, is_admin, ver, created_at) VALUES (?,?,1,?,?)",
                          (user, _hash(pw), secrets.token_hex(16), int(time.time()))).lastrowid
        con.execute("UPDATE groups SET user_id=? WHERE user_id IS NULL", (uid,))
        con.execute("UPDATE links SET user_id=? WHERE user_id IS NULL", (uid,))
        con.execute("DELETE FROM settings WHERE key='setup_code'")
        row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        con.execute("COMMIT")
    finally:
        if con.in_transaction:
            con.execute("ROLLBACK")
        con.close()
    _sign_in(row)
    session.permanent = True
    return jsonify(ok=True), 201


@app.post("/api/login")
def api_login():
    d = request.get_json(force=True, silent=True) or {}
    ip = _client()
    wait = _wait_seconds(ip)
    if wait:
        return jsonify(error=f"Too many attempts. Try again in {wait} seconds."), 429
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE username=?", (str(d.get("username", "")).strip(),)).fetchone()
    ok = check_password_hash(row["pw_hash"] if row else _DUMMY_HASH, str(d.get("password", ""))) and row is not None
    _note_login(ip, ok)
    if not ok:
        return jsonify(error="Wrong username or password."), 401
    _sign_in(row)
    session.permanent = bool(d.get("remember"))  # otherwise the cookie ends with the browser session
    return jsonify(ok=True)


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)


@app.post("/api/account")
def update_account():
    """Change your own username and/or password. Needs the current password, except
    inside Home Assistant (already signed in there; an account made by HA has none
    until one is set here, for the direct port)."""
    d = request.get_json(force=True, silent=True) or {}
    if not via_ingress() and not check_password_hash(g.user["pw_hash"], str(d.get("current_password", ""))):
        return jsonify(error="The current password is not correct."), 403
    user, pw = str(d.get("username", "")).strip(), str(d.get("password", ""))
    problem = _check_new_credentials(user, pw, need_password=bool(pw))
    if problem:
        return jsonify(error=problem), 400
    with db() as c:
        try:
            c.execute("UPDATE users SET username=? WHERE id=?", (user, me()))
        except sqlite3.IntegrityError:
            return jsonify(error="That username is already taken."), 409
        if pw:  # new value signs every other device out
            c.execute("UPDATE users SET pw_hash=?, ver=? WHERE id=?", (_hash(pw), secrets.token_hex(16), me()))
        row = c.execute("SELECT * FROM users WHERE id=?", (me(),)).fetchone()
    if not via_ingress():
        _sign_in(row)
        session.permanent = True
    return jsonify(ok=True)


@app.post("/api/apikey")
def make_api_key():
    """Create (or replace) your API key. It is shown once; only its hash is stored."""
    key = "tm_" + secrets.token_urlsafe(32)
    with db() as c:
        c.execute("UPDATE users SET api_key_hash=? WHERE id=?", (hashlib.sha256(key.encode()).hexdigest(), me()))
    return jsonify(key=key)


@app.delete("/api/apikey")
def drop_api_key():
    with db() as c:
        c.execute("UPDATE users SET api_key_hash='' WHERE id=?", (me(),))
    return jsonify(ok=True)


# ------------------------------------------------------------ admin: users
def _admins(c):
    return c.execute("SELECT COUNT(*) FROM users WHERE is_admin=1").fetchone()[0]


@app.get("/api/users")
def list_users():
    with db() as c:
        rows = c.execute("SELECT u.id, u.username, u.is_admin, u.created_at, "
                         "(SELECT COUNT(*) FROM links l WHERE l.user_id=u.id) AS links "
                         "FROM users u ORDER BY u.username").fetchall()
    return jsonify(users=[dict(r) | {"me": r["id"] == me()} for r in rows])


@app.post("/api/users")
def create_user():
    d = request.get_json(force=True, silent=True) or {}
    user, pw = str(d.get("username", "")).strip(), str(d.get("password", ""))
    problem = _check_new_credentials(user, pw)
    if problem:
        return jsonify(error=problem), 400
    with db() as c:
        try:
            uid = c.execute("INSERT INTO users (username, pw_hash, is_admin, ver, created_at) VALUES (?,?,?,?,?)",
                            (user, _hash(pw), 1 if d.get("is_admin") else 0, secrets.token_hex(16),
                             int(time.time()))).lastrowid
        except sqlite3.IntegrityError:
            return jsonify(error="That username is already taken."), 409
    return jsonify(id=uid), 201


@app.patch("/api/users/<int:uid>")
def update_user(uid):
    """Rename, set a new password (signs that user out everywhere) or change admin rights."""
    d = request.get_json(force=True, silent=True) or {}
    user = str(d.get("username") or "").strip() if "username" in d else None
    pw = str(d.get("password") or "")
    make = (1 if d["is_admin"] else 0) if "is_admin" in d else None
    if user is not None and _check_new_credentials(user, "", need_password=False):
        return jsonify(error=_check_new_credentials(user, "", need_password=False)), 400
    if pw and len(pw) < 8:
        return jsonify(error="The password needs at least 8 characters."), 400
    with db() as c:  # everything is checked before the first change
        row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not row:
            return jsonify(error="Not found"), 404
        if make == 0 and row["is_admin"] and _admins(c) <= 1:
            return jsonify(error="TileMark needs at least one admin."), 400
        if user is not None and c.execute("SELECT 1 FROM users WHERE username=? AND id != ?", (user, uid)).fetchone():
            return jsonify(error="That username is already taken."), 409
        if user is not None:
            c.execute("UPDATE users SET username=? WHERE id=?", (user, uid))
        if pw:
            c.execute("UPDATE users SET pw_hash=?, ver=? WHERE id=?", (_hash(pw), secrets.token_hex(16), uid))
        if make is not None:
            c.execute("UPDATE users SET is_admin=? WHERE id=?", (make, uid))
        fresh = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if uid == me():  # keep the admin who changed their own password signed in here
        _sign_in(fresh)
    return jsonify(ok=True)


@app.delete("/api/users/<int:uid>")
def delete_user(uid):
    """Removes the account with all its links, groups and pictures."""
    if uid == me():
        return jsonify(error="You cannot remove your own account."), 400
    with db() as c:
        if not c.execute("SELECT 1 FROM users WHERE id=?", (uid,)).fetchone():
            return jsonify(error="Not found"), 404
        thumbs = [r["thumb"] for r in c.execute("SELECT thumb FROM links WHERE user_id=? AND thumb != ''", (uid,))]
        c.execute("DELETE FROM links WHERE user_id=?", (uid,))
        c.execute("DELETE FROM groups WHERE user_id=?", (uid,))
        c.execute("DELETE FROM users WHERE id=?", (uid,))
    for name in thumbs:
        _remove_thumb(name)
    return jsonify(ok=True)


# --------------------------------------------------------------------- api
@app.get("/")
def index():
    return send_from_directory(PAGES, "index.html", max_age=0)


@app.get("/thumbs/<path:name>")
def thumbs(name):
    name = os.path.basename(name)
    with db() as c:
        mine = c.execute("SELECT 1 FROM links WHERE thumb=? AND user_id=?", (name, me())).fetchone()
    if not mine:
        return jsonify(error="Not found"), 404
    resp = send_from_directory(THUMB_DIR, name, max_age=31536000)
    resp.cache_control.public = False  # never kept by a shared cache: it belongs to one user
    resp.cache_control.private = True
    return resp


PREF_KEYS = {"layout": ("panel", "sections"), "theme": ("system", "light", "dark"),
             "thumb": ("s", "m", "l"), "open": ("new", "same")}
SORT_MODES = ("manual", "newest", "oldest", "name", "site")


def _prefs(uid):
    try:
        return json.loads(get_user_setting(uid, "ui", "{}"))
    except ValueError:
        return {}


@app.get("/api/state")
def state():
    uid = me()
    with db() as c:
        groups = [dict(r) for r in c.execute("SELECT * FROM groups WHERE user_id=? ORDER BY position, id", (uid,))]
        links = [dict(r) for r in c.execute("SELECT * FROM links WHERE user_id=? ORDER BY position, id DESC", (uid,))]
    with _check_lock:
        check = dict(_check)
    if not (check["uid"] == uid or (check["uid"] is None and g.user["is_admin"])):
        check.update(done=0, total=0)  # someone else's check: only say that one is running
    check.pop("uid")
    check.update(enabled=get_setting("linkcheck", "on") == "on",
                 last=max(int(get_setting("linkcheck_last", "0")), int(get_user_setting(uid, "linkcheck_last", "0"))))
    out = dict(groups=groups, links=links, check=check, prefs=_prefs(uid),
               me={"username": g.user["username"], "is_admin": bool(g.user["is_admin"])})
    if g.user["is_admin"]:
        out["admin"] = {"fetch_private": fetch_private(), "daily_backup": daily_backup_on(),
                        "backup_last": int(get_setting("backup_last", "0")), "backups": len(list_backups()),
                        "addon": HA_ADDON}
    return jsonify(out)


@app.put("/api/prefs")
def save_prefs():
    """Layout, appearance and sort choices, kept on the server so every device of
    this user sees the same."""
    d = request.get_json(force=True, silent=True) or {}
    prefs = _prefs(me())
    for key, allowed in PREF_KEYS.items():
        if d.get(key) in allowed:
            prefs[key] = d[key]
    if "defgroup" in d:  # default group of the "add" box: one of your groups, or none
        with db() as c:
            gid = own_group(c, me(), d["defgroup"]) if d["defgroup"] else None
        prefs["defgroup"] = str(gid) if gid else ""
    if isinstance(d.get("sorts"), dict):
        prefs["sorts"] = {str(k)[:40]: v for k, v in list(d["sorts"].items())[:500] if v in SORT_MODES}
    set_user_setting(me(), "ui", json.dumps(prefs))
    return jsonify(ok=True, prefs=prefs)


@app.post("/api/settings")
def save_settings():
    """Settings for the whole installation (admin only)."""
    d = request.get_json(force=True, silent=True) or {}
    if "linkcheck" in d:
        set_setting("linkcheck", "on" if d["linkcheck"] else "off")
    if "fetch_private" in d:
        set_setting("fetch_private", "on" if d["fetch_private"] else "off")
    if "daily_backup" in d:
        set_setting("daily_backup", "on" if d["daily_backup"] else "off")
    return jsonify(ok=True)


@app.post("/api/linkcheck")
def start_link_check():
    if not run_link_check(me()):
        return jsonify(error="A check is already running."), 409
    return jsonify(ok=True)


def own_link(c, link_id):
    return c.execute("SELECT * FROM links WHERE id=? AND user_id=?", (link_id, me())).fetchone()


@app.post("/api/links/<int:link_id>/thumb")
def set_thumb(link_id):
    """Use an uploaded picture for this link, in place of the fetched one."""
    f = request.files.get("file")
    with db() as c:
        row = own_link(c, link_id)
    if not row or not f:
        return jsonify(error="Not found" if not row else "Choose a picture."), 404 if not row else 400
    name = _save_thumb(link_id, f.read(20_000_000), "image")
    if not name:
        return jsonify(error="That file is not a usable picture (it may be too small or not an image)."), 400
    with db() as c:
        c.execute("UPDATE links SET thumb=?, thumb_kind='image', custom_thumb=1 WHERE id=? AND user_id=?",
                  (name, link_id, me()))
    if row["thumb"] and row["thumb"] != name:
        _remove_thumb(row["thumb"])
    return jsonify(ok=True)


@app.delete("/api/links/<int:link_id>/thumb")
def drop_thumb(link_id):
    """Forget the own picture and fetch the site's one again."""
    with db() as c:
        n = c.execute("UPDATE links SET custom_thumb=0, status='pending' WHERE id=? AND user_id=?",
                      (link_id, me())).rowcount
    if not n:
        return jsonify(error="Not found"), 404
    queue(link_id)
    return jsonify(ok=True)


@app.post("/api/links")
def create_link():
    d = request.get_json(force=True, silent=True) or {}
    url = normalize_url(d.get("url"))
    if not url:
        return jsonify(error="That does not look like a web link."), 400
    title, note = str(d.get("title") or "").strip()[:300], str(d.get("note") or "").strip()[:2000]
    uid = me()
    with db() as c:
        gid = own_group(c, uid, d.get("group_id")) if d.get("group_id") else None
        if gid is None and str(d.get("group") or "").strip():  # by name; created if it is new
            gid = get_or_create_group(c, uid, str(d["group"]))
        link_id = add_link(c, uid, url, gid, title)
        if link_id is not None and note:
            c.execute("UPDATE links SET note=? WHERE id=?", (note, link_id))
    if link_id is None:
        return jsonify(error="This link is already saved."), 409
    queue(link_id)
    return jsonify(id=link_id), 201


@app.get("/api/groups")
def list_groups():
    """Group names only - what the "Save to TileMark" window and API-key clients need."""
    with db() as c:
        return jsonify(groups=[dict(r) for r in c.execute(
            "SELECT id, name, color FROM groups WHERE user_id=? ORDER BY position, id", (me(),))])


@app.post("/api/links/<int:link_id>/opened")
def opened_link(link_id):
    with db() as c:
        c.execute("UPDATE links SET opened_at=? WHERE id=? AND user_id=?", (int(time.time()), link_id, me()))
    return jsonify(ok=True)


def _ids(d):
    return list(dict.fromkeys(int(i) for i in d.get("ids", []) if str(i).isdigit()))


def _own_ids(c, ids):
    """Keep only the ids of this user's links (order kept)."""
    if not ids:
        return []
    mine = {r["id"] for r in c.execute(
        f"SELECT id FROM links WHERE user_id=? AND id IN ({','.join('?' * len(ids))})", [me()] + ids)}
    return [i for i in ids if i in mine]


@app.post("/api/links/order")
def order_links():
    """Body: {"ids": [...]} - these links, in the order they should appear. They
    swap places among themselves only, so other links keep their position."""
    with db() as c:
        ids = _own_ids(c, _ids(request.get_json(force=True, silent=True) or {}))
        rows = {r["id"]: r["position"] for r in
                c.execute(f"SELECT id, position FROM links WHERE id IN ({','.join('?' * len(ids))})", ids)} if ids else {}
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
    thumbs = []
    with db() as c:
        ids = _own_ids(c, _ids(d))
        if not ids:
            return jsonify(error="Nothing selected."), 400
        marks = ",".join("?" * len(ids))
        if d.get("delete"):
            thumbs = [r["thumb"] for r in c.execute(f"SELECT thumb FROM links WHERE id IN ({marks})", ids) if r["thumb"]]
            c.execute(f"DELETE FROM links WHERE id IN ({marks})", ids)
        elif "group_id" in d:
            gid = None
            if d["group_id"]:
                gid = own_group(c, me(), d["group_id"])
                if gid is None:
                    return jsonify(error="That group no longer exists."), 404
            c.execute(f"UPDATE links SET group_id=? WHERE id IN ({marks})", [gid] + ids)
        elif d.get("refresh"):
            c.execute(f"UPDATE links SET status='pending' WHERE id IN ({marks})", ids)
        else:
            return jsonify(error="Nothing to do."), 400
    for name in thumbs:
        _remove_thumb(name)
    if d.get("refresh") and not d.get("delete"):
        for link_id in ids:
            queue(link_id)
    return jsonify(ok=True, count=len(ids))


@app.patch("/api/links/<int:link_id>")
def update_link(link_id):
    d = request.get_json(force=True, silent=True) or {}
    refetch = False
    with db() as c:  # everything is checked before the first change
        row = own_link(c, link_id)
        if not row:
            return jsonify(error="Not found"), 404
        gid = own_group(c, me(), d.get("group_id")) if d.get("group_id") else None
        if d.get("group_id") and gid is None:
            return jsonify(error="That group no longer exists."), 404
        url = normalize_url(d["url"]) if "url" in d else row["url"]
        if not url:
            return jsonify(error="That does not look like a web link."), 400
        if url != row["url"] and c.execute("SELECT 1 FROM links WHERE user_id=? AND url=?", (me(), url)).fetchone():
            return jsonify(error="This link is already saved."), 409
        if "title" in d:
            t = (d["title"] or "").strip()[:300]
            if t != row["title"]:
                c.execute("UPDATE links SET title=?, custom_title=? WHERE id=?", (t, 1 if t else 0, link_id))
                refetch = refetch or not t
        if "group_id" in d:
            c.execute("UPDATE links SET group_id=? WHERE id=?", (gid, link_id))
        if "note" in d:
            c.execute("UPDATE links SET note=? WHERE id=?", (str(d["note"] or "").strip()[:2000], link_id))
        if "pinned" in d:
            c.execute("UPDATE links SET pinned=? WHERE id=?", (1 if d["pinned"] else 0, link_id))
        if url != row["url"]:
            c.execute("UPDATE links SET url=?, status='pending' WHERE id=?", (url, link_id))
            refetch = True
    if refetch:
        queue(link_id)
    return jsonify(ok=True)


@app.post("/api/links/<int:link_id>/refresh")
def refresh_link(link_id):
    with db() as c:
        n = c.execute("UPDATE links SET status='pending' WHERE id=? AND user_id=?", (link_id, me())).rowcount
    if not n:
        return jsonify(error="Not found"), 404
    queue(link_id)
    return jsonify(ok=True)


@app.delete("/api/links/<int:link_id>")
def delete_link(link_id):
    with db() as c:
        row = own_link(c, link_id)
        c.execute("DELETE FROM links WHERE id=? AND user_id=?", (link_id, me()))
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
        gid = get_or_create_group(c, me(), d.get("name"))
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
        known = [r["id"] for r in c.execute("SELECT id FROM groups WHERE user_id=? ORDER BY position, id", (me(),))]
        ordered = [i for i in dict.fromkeys(ids) if i in known] + [i for i in known if i not in ids]
        for pos, gid in enumerate(ordered, 1):
            c.execute("UPDATE groups SET position=? WHERE id=?", (pos, gid))
    return jsonify(ok=True)


@app.patch("/api/groups/<int:gid>")
def update_group(gid):
    d = request.get_json(force=True, silent=True) or {}
    with db() as c:
        if own_group(c, me(), gid) is None:
            return jsonify(error="Not found"), 404
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
        if own_group(c, me(), gid) is None:
            return jsonify(error="Not found"), 404
        if request.args.get("links") == "1":
            for r in c.execute("SELECT thumb FROM links WHERE group_id=? AND user_id=?", (gid, me())).fetchall():
                if r["thumb"]:
                    _remove_thumb(r["thumb"])
            c.execute("DELETE FROM links WHERE group_id=? AND user_id=?", (gid, me()))
        c.execute("DELETE FROM groups WHERE id=? AND user_id=?", (gid, me()))
    return jsonify(ok=True)


@app.post("/api/import")
def import_links():
    text = request.form.get("text", "")
    f = request.files.get("file")
    if f:
        text += "\n" + f.read().decode("utf-8", errors="replace")
    is_bookmarks = bool(re.search(r"<a\b[^>]*href", text, re.I))
    items = parse_bookmarks_html(text) if is_bookmarks else parse_plain(text)
    added, skipped, new_ids, uid = 0, 0, [], me()
    with db() as c:
        target = own_group(c, uid, request.form.get("group_id")) if request.form.get("group_id") else None
        for raw, title, folder in items:
            url = normalize_url(raw)
            if not url:
                skipped += 1
                continue
            gid = target or (get_or_create_group(c, uid, folder) if folder else None)
            link_id = add_link(c, uid, url, gid, title, top=False)
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
        groups = c.execute("SELECT * FROM groups WHERE user_id=? ORDER BY position, id", (me(),)).fetchall()
        links = c.execute("SELECT * FROM links WHERE user_id=? ORDER BY position, id DESC", (me(),)).fetchall()

    def rows(gid, pad):
        return [f'{pad}<DT><A HREF="{e(l["url"])}" ADD_DATE="{l["created_at"]}">{e(l["title"] or l["url"])}</A>'
                for l in links if l["group_id"] == gid]

    for grp in groups:
        out += [f'    <DT><H3>{e(grp["name"])}</H3>', "    <DL><p>", *rows(grp["id"], "        "), "    </DL><p>"]
    out += rows(None, "    ") + ["</DL><p>", ""]
    return Response("\n".join(out), mimetype="text/html",
                    headers={"Content-Disposition": "attachment; filename=tilemark-bookmarks.html"})


# ------------------------------------------------------- backup and restore
# A backup holds one user's links, groups and thumbnails: a zip with a small
# database (tables "groups" and "links") and the thumbnails. With a password it is
# wrapped as: MAGIC + 16-byte salt + 12-byte nonce + AES-256-GCM(zip), key =
# scrypt(password). Accounts, passwords and API keys are never in a backup.
# Backups made under the app's previous name use LEGACY_MAGIC and a database named
# LEGACY_DB in the zip; they restore exactly like new ones.
MAGIC = b"TILEMARK-BACKUP-1\n"
BACKUP_DB = "tilemark.db"
LEGACY_MAGIC = b"LINK" + b"BOARD-BACKUP-1\n"
LEGACY_DB = "link" + "board.db"
MAX_BACKUP_DB = 512 * 1024 * 1024


def _key(password, salt):
    return Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(password.encode("utf-8"))


def make_backup(uid, password=""):
    with tempfile.TemporaryDirectory() as tmp:
        snap = os.path.join(tmp, "tilemark.db")
        cols = ",".join(LINK_COLS)
        con = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute("ATTACH DATABASE ? AS b", (snap,))
            con.execute("BEGIN")  # one transaction: a consistent copy, even while the app is in use
            con.execute("CREATE TABLE b.groups AS SELECT id, name, color, position FROM main.groups WHERE user_id=?", (uid,))
            con.execute(f"CREATE TABLE b.links AS SELECT {cols} FROM main.links WHERE user_id=?", (uid,))
            con.execute("CREATE TABLE b.settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            thumbs = [r["thumb"] for r in con.execute("SELECT thumb FROM b.links WHERE thumb != ''")]
            con.execute("COMMIT")
            con.execute("DETACH DATABASE b")
        finally:
            con.close()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, BACKUP_DB)
            for name in sorted(set(thumbs)):
                path = os.path.join(THUMB_DIR, os.path.basename(name))
                if os.path.isfile(path):
                    z.write(path, "thumbs/" + os.path.basename(name), zipfile.ZIP_STORED)
    data = buf.getvalue()
    if password:
        salt, nonce = os.urandom(16), os.urandom(12)
        data = MAGIC + salt + nonce + AESGCM(_key(password, salt)).encrypt(nonce, data, MAGIC)
    return data


class RestoreError(Exception):
    pass


def restore_backup(uid, data, password=""):
    """Replace this user's links and groups with the ones in the backup. Ids are
    given anew (other users' ids may be taken), so groups and pictures are mapped."""
    magic = next((m for m in (MAGIC, LEGACY_MAGIC) if data.startswith(m)), None)
    if magic:
        if not password:
            raise RestoreError("This backup is protected. Enter its password.")
        salt, nonce, body = data[len(magic):len(magic) + 16], data[len(magic) + 16:len(magic) + 28], data[len(magic) + 28:]
        try:
            data = AESGCM(_key(password, salt)).decrypt(nonce, body, magic)
        except InvalidTag:
            raise RestoreError("Wrong password, or the backup file is damaged.")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        names = z.namelist()
        db_name = next((n for n in (BACKUP_DB, LEGACY_DB) if n in names), None)
        if db_name is None:
            raise KeyError(BACKUP_DB)
        if z.getinfo(db_name).file_size > MAX_BACKUP_DB:
            raise RestoreError("The backup's database is too large.")
    except (zipfile.BadZipFile, KeyError):
        raise RestoreError("This is not a TileMark backup file.")
    with tempfile.TemporaryDirectory() as tmp:
        snap = os.path.join(tmp, "restore.db")
        with open(snap, "wb") as f:
            f.write(z.read(db_name))
        try:
            old = sqlite3.connect(snap)
            old.row_factory = sqlite3.Row
            groups = [dict(r) for r in old.execute("SELECT * FROM groups")]
            links = [dict(r) for r in old.execute("SELECT * FROM links")]
            old.close()
        except sqlite3.Error:
            raise RestoreError("The backup's database cannot be read.")
        files = {}
        for info in z.infolist():
            name = os.path.basename(info.filename)
            if (info.filename.startswith("thumbs/") and re.fullmatch(r"[\w.-]+\.(webp|png)", name)
                    and info.file_size <= 20_000_000):
                files[name] = info
        moves = []
        with db() as c:  # one transaction: either everything is replaced or nothing
            l_cols = [r["name"] for r in c.execute("PRAGMA table_info(links)")
                      if r["name"] not in ("id", "user_id", "group_id", "thumb")]
            old_thumbs = [r["thumb"] for r in c.execute("SELECT thumb FROM links WHERE user_id=? AND thumb != ''", (uid,))]
            c.execute("DELETE FROM links WHERE user_id=?", (uid,))
            c.execute("DELETE FROM groups WHERE user_id=?", (uid,))
            gmap = {}
            for grp in sorted(groups, key=lambda r: (r.get("position", r["id"]), r["id"])):
                name = str(grp.get("name") or "").strip()[:60]
                if not name:
                    continue
                gid = get_or_create_group(c, uid, name)
                if _color(grp.get("color")):
                    c.execute("UPDATE groups SET color=?, position=? WHERE id=?",
                              (grp["color"], grp.get("position", grp["id"]), gid))
                gmap[grp["id"]] = gid
            restored = 0
            for row in links:
                row.setdefault("position", -row["id"])
                use = [k for k in l_cols if k in row]
                try:
                    new_id = c.execute(
                        f"INSERT INTO links (user_id, group_id, {','.join(use)}) VALUES (?,?,{','.join('?' * len(use))})",
                        [uid, gmap.get(row.get("group_id"))] + [row[k] for k in use]).lastrowid
                except sqlite3.IntegrityError:  # the same address twice in the file
                    continue
                restored += 1
                thumb = row.get("thumb") or ""
                if thumb in files:
                    new_name = f"{new_id}-{int(time.time() * 1000)}-{secrets.token_hex(3)}{os.path.splitext(thumb)[1]}"
                    path = os.path.join(tmp, new_name)
                    with open(path, "wb") as f:
                        f.write(z.read(files[thumb]))
                    moves.append((path, new_name))
                    c.execute("UPDATE links SET thumb=? WHERE id=?", (new_name, new_id))
                elif thumb:
                    c.execute("UPDATE links SET thumb='', thumb_kind='', custom_thumb=0 WHERE id=?", (new_id,))
            c.execute("UPDATE links SET status='error' WHERE status='pending' AND user_id=?", (uid,))
            for path, new_name in moves:  # inside the transaction: a failed copy undoes the restore
                shutil.move(path, os.path.join(THUMB_DIR, new_name))
        for name in old_thumbs:
            _remove_thumb(name)
    return restored, len(gmap)


# Daily copy of the whole installation (all accounts) in data/backups, the last
# KEEP_BACKUPS kept. It holds the database and the pictures people uploaded
# themselves; fetched thumbnails are left out (they come back with ↻) so seven
# copies stay small. Restoring: stop TileMark, unzip one into the data folder,
# start it again. In the Home Assistant add-on it is off by default, because HA's
# own backups already contain the add-on's data.
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
BACKUP_EVERY = 24 * 3600 - 600
KEEP_BACKUPS = 7


def daily_backup_on():
    return get_setting("daily_backup", "off" if HA_ADDON else "on") == "on"


def list_backups():
    try:
        return sorted(n for n in os.listdir(BACKUP_DIR) if re.fullmatch(r"tilemark-\d{4}-\d{2}-\d{2}\.zip", n))
    except OSError:
        return []


def daily_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    final = os.path.join(BACKUP_DIR, time.strftime("tilemark-%Y-%m-%d.zip"))
    part = final + ".part"
    with tempfile.TemporaryDirectory() as tmp:
        snap = os.path.join(tmp, "tilemark.db")
        src, dst = sqlite3.connect(DB_PATH, timeout=30), sqlite3.connect(snap)
        with dst:
            src.backup(dst)  # consistent copy, even while the app is in use
        src.close()
        own = [r[0] for r in dst.execute("SELECT thumb FROM links WHERE custom_thumb=1 AND thumb != ''")]
        dst.close()
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(snap, BACKUP_DB)
            for name in sorted(set(own)):
                path = os.path.join(THUMB_DIR, os.path.basename(name))
                if os.path.isfile(path):
                    z.write(path, "thumbs/" + os.path.basename(name), zipfile.ZIP_STORED)
    os.replace(part, final)
    for old in list_backups()[:-KEEP_BACKUPS]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass
    set_setting("backup_last", str(int(time.time())))
    return final


@app.post("/api/backup")
def api_backup():
    d = request.get_json(force=True, silent=True) or {}
    password = str(d.get("password", ""))
    data = make_backup(me(), password)
    name = "tilemark-backup-" + time.strftime("%Y-%m-%d") + (".tmk" if password else ".zip")
    return Response(data, mimetype="application/octet-stream",
                    headers={"Content-Disposition": f"attachment; filename={name}", "X-Filename": name})


@app.post("/api/restore")
def api_restore():
    f = request.files.get("file")
    if not f:
        return jsonify(error="Choose a backup file."), 400
    try:
        links, groups = restore_backup(me(), f.read(), request.form.get("password", ""))
    except RestoreError as e:
        return jsonify(error=str(e)), 400
    return jsonify(ok=True, links=links, groups=groups)


# -------------------------------------------------------------------- start
def reset_login(username=None):
    """docker exec tilemark python app.py reset-login [username]
    Gives that user (default: the first admin) a new random password and prints it."""
    with db() as c:
        if username:
            row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        else:
            row = c.execute("SELECT * FROM users WHERE is_admin=1 ORDER BY id LIMIT 1").fetchone()
        if not row:
            return None, None
        pw = secrets.token_urlsafe(12)
        c.execute("UPDATE users SET pw_hash=?, ver=? WHERE id=?", (_hash(pw), secrets.token_hex(16), row["id"]))
    return row["username"], pw


init_db()
if not get_setting("secret_key"):
    set_setting("secret_key", secrets.token_hex(32))
app.secret_key = get_setting("secret_key")
app.config.update(SESSION_COOKIE_NAME="tilemark", SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                  PERMANENT_SESSION_LIFETIME=timedelta(days=30))
_CLI = sys.argv[1:2] in (["reset-login"], ["setup-code"])
if not _CLI and not os.environ.get("TILEMARK_NO_WORKERS"):
    if setup_needed():  # (as an add-on, opening it from the HA sidebar also creates the first account)
        print_setup_code()
    threading.Thread(target=_check_scheduler, daemon=True).start()
    with db() as _c:  # once: fetch again the titles saved from a bot-check page before 1.2.1
        if not _c.execute("SELECT 1 FROM settings WHERE key='wall_titles_fixed'").fetchone():
            for _r in _c.execute("SELECT id, title FROM links WHERE custom_title=0").fetchall():
                if is_wall_title(_r["title"]):
                    _c.execute("UPDATE links SET status='pending' WHERE id=?", (_r["id"],))
            _c.execute("INSERT INTO settings (key, value) VALUES ('wall_titles_fixed', '1')")
    with db() as _c:  # pick up anything interrupted by a restart
        for _r in _c.execute("SELECT id FROM links WHERE status='pending'").fetchall():
            queue(_r["id"])

if __name__ == "__main__":
    if sys.argv[1:2] == ["setup-code"]:
        if not setup_needed():
            print("TileMark already has an account; no setup code is needed. Forgot a password? Use reset-login.")
            sys.exit(1)
        print(f"Setup code: {setup_code()}")
        sys.exit(0)
    if _CLI:
        who, new_pw = reset_login(sys.argv[2] if len(sys.argv) > 2 else None)
        if not who:
            print("No such account. With no accounts at all, open TileMark to create the first one.")
            sys.exit(1)
        print(f"New password for {who}: {new_pw}\nSign in with it, then change it in Settings. "
              "Every device of this account has been signed out.")
        sys.exit(0)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
