"""TileMark - a tiny self-hosted page for your links, with thumbnails and groups."""
import base64
import hmac
import html
import ipaddress
import hashlib
import struct
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
from urllib.parse import unquote, urljoin, urlparse, urlsplit

import requests
import segno
import paho.mqtt.client as paho
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
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey

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
APP_VERSION = os.environ.get("TILEMARK_VERSION", "dev")  # set when the image is built

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
    with db() as c:  # columns and tables added after 1.1.0 (plain additions, no rebuild)
        ucols = [r["name"] for r in c.execute("PRAGMA table_info(users)")]
        for col, ddl in (("ha_user", "TEXT NOT NULL DEFAULT ''"), ("totp_secret", "TEXT NOT NULL DEFAULT ''"),
                         ("totp_last", "INTEGER NOT NULL DEFAULT 0"), ("recovery", "TEXT NOT NULL DEFAULT ''"),
                         ("uk_pub", "TEXT NOT NULL DEFAULT ''"), ("uk_priv", "TEXT NOT NULL DEFAULT ''")):
            if col not in ucols:
                c.execute(f"ALTER TABLE users ADD COLUMN {col} {ddl}")
        lcols = [r["name"] for r in c.execute("PRAGMA table_info(links)")]
        for col in ("ukey", "final_key"):
            if col not in lcols:
                c.execute(f"ALTER TABLE links ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
        c.execute("CREATE INDEX IF NOT EXISTS links_ukey ON links(user_id, ukey)")
        c.execute("""CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            created_at INTEGER NOT NULL,
            last_seen INTEGER NOT NULL,
            ua TEXT NOT NULL DEFAULT '',
            ip TEXT NOT NULL DEFAULT '')""")
        c.execute("""CREATE TABLE IF NOT EXISTS bk_grants (
            user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            uk_pub TEXT NOT NULL,
            sealed TEXT NOT NULL)""")
        for r in c.execute("SELECT id, url FROM links WHERE ukey = ''").fetchall():  # links saved before 2.1
            c.execute("UPDATE links SET ukey=? WHERE id=?", (url_key(r["url"]), r["id"]))


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
    return clean_url(raw)


# Tracking parameters say who shared a link or which campaign it came from; they do
# not change the page. They are removed when a link is saved, so the same page saved
# twice (once from a newsletter, once from a friend) is recognised as one.
TRACKING = re.compile(r"^(utm_[\w.-]*|fbclid|gclid|gclsrc|dclid|gbraid|wbraid|msclkid|yclid|twclid|ttclid|li_fat_id|"
                      r"mc_cid|mc_eid|_hsenc|_hsmi|mkt_tok|igshid|igsh|ref_src|ref_url|vero_id|oly_anon_id|"
                      r"oly_enc_id|wt\.mc_id|_ga|_gl)$", re.I)
# Only meaningful as tracking on these sites ("si" is a real parameter elsewhere).
SITE_TRACKING = {"youtube.com": ("si", "feature", "pp"), "youtu.be": ("si", "feature"), "spotify.com": ("si", "context"),
                 "instagram.com": ("igsh",), "x.com": ("s", "t"), "twitter.com": ("s", "t")}


def _host_of(p):
    h = (p.hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _tracking(name, host):
    name = unquote(name).strip()
    if TRACKING.match(name):
        return True
    return any((host == site or host.endswith("." + site)) and name.lower() in names for site, names in SITE_TRACKING.items())


def _query_parts(query, host):
    """The query split into its original pieces, without tracking parameters (encoding untouched)."""
    return [part for part in query.split("&") if part and not _tracking(part.split("=", 1)[0], host)]


def clean_url(url):
    p = urlsplit(url)
    if not p.query:
        return url
    parts = _query_parts(p.query, _host_of(p))
    if len(parts) == len([x for x in p.query.split("&") if x]):
        return url
    return p._replace(query="&".join(parts)).geturl()


def url_key(url):
    """What two addresses must share to count as the same page: the scheme, a leading
    "www.", the default port, a trailing slash, tracking parameters and the order of
    the parameters do not matter, and YouTube's short forms are the same video."""
    try:
        p = urlsplit(url)
        port = p.port
    except ValueError:
        return url
    host = _host_of(p)
    path, query, frag = p.path.rstrip("/"), p.query, p.fragment
    if host in ("m.youtube.com", "music.youtube.com"):
        host = "youtube.com"
    if host == "youtu.be" and path.strip("/"):
        host, query, path = "youtube.com", "v=" + path.strip("/").split("/")[0], "/watch"
    elif host == "youtube.com":
        m = re.match(r"^/(shorts|live|embed)/([\w-]+)", path)
        if m:
            query, path = "v=" + m.group(2), "/watch"
        if path == "/watch":  # a video is its v= parameter; a start time is still the same video
            query = "&".join(x for x in query.split("&") if x.split("=", 1)[0] in ("v", "list"))
    parts = sorted(_query_parts(query, host))
    port_part = f":{port}" if port and port not in (80, 443) else ""
    key = host + port_part + path + ("?" + "&".join(parts) if parts else "")
    if frag.startswith(("/", "!")):  # page routes in single-page apps; other #anchors are the same page
        key += "#" + frag
    return key


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
            "INSERT INTO links (user_id, url, title, group_id, custom_title, created_at, position, ukey) VALUES (?,?,?,?,?,?,?,?)",
            (uid, url, title, group_id, 0, int(time.time()), lo - 1 if top else hi + 1, url_key(url))).lastrowid
    except sqlite3.IntegrityError:
        return None


def find_duplicate(c, uid, key, exclude_id=0):
    """A link of this user that is the same page (same key, or one that ended up there after redirects)."""
    return c.execute("SELECT l.id, l.url, l.title, g.name AS group_name FROM links l LEFT JOIN groups g ON g.id = l.group_id "
                     "WHERE l.user_id=? AND l.id != ? AND (l.ukey=? OR l.final_key=?) ORDER BY l.id LIMIT 1",
                     (uid, exclude_id, key, key)).fetchone()


def _dup_info(row):
    return {"id": row["id"], "url": row["url"], "title": row["title"], "group": row["group_name"] or ""}


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
        final_key = url_key(clean_url(info["final"])) if info.get("final") else ""
        final_key = "" if final_key == cur["ukey"] else final_key  # only kept when a redirect led elsewhere
        c.execute("UPDATE links SET title=?, description=?, thumb=?, thumb_kind=?, status=?, final_key=? WHERE id=?",
                  (new_title, desc[:500] or cur["description"], thumb, kind, status, final_key, link_id))
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
_check = {"running": False, "done": 0, "total": 0, "uid": None, "new_broken": 0}
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
    newly = False
    with db() as c:
        if result == "unknown":
            c.execute("UPDATE links SET checked_at=? WHERE id=?", (int(time.time()), link_id))
        else:
            was = c.execute("SELECT broken FROM links WHERE id=?", (link_id,)).fetchone()
            newly = result == "broken" and was is not None and not was["broken"]
            c.execute("UPDATE links SET broken=?, checked_at=? WHERE id=?",
                      (1 if result == "broken" else 0, int(time.time()), link_id))
    with _check_lock:
        _check["done"] += 1
        _check["new_broken"] += 1 if newly else 0


def run_link_check(uid=None):
    """Check links in the background: one user's (the "Check now" button) or everyone's
    (the weekly run, uid None). False if a check is already running."""
    with _check_lock:
        if _check["running"]:
            return False
        _check.update(running=True, done=0, total=0, uid=uid, new_broken=0)

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
                with _check_lock:
                    checked, new_broken = _check["total"], _check["new_broken"]
                mqtt.check_finished(checked, new_broken)  # the weekly check of every account
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



# ------------------------------------------------------- Home Assistant via MQTT
# With MQTT on, TileMark appears in Home Assistant as a device "TileMark" (MQTT
# discovery, no YAML): sensors for the number of links and broken links (all
# accounts together; counts only, never links), the time of the last weekly check,
# and an event entity that fires when the weekly check finishes, for automations
# such as a notification. As an add-on, Home Assistant's own broker is used when no
# broker is filled in (the add-on asks the Supervisor for it).
def supervisor_mqtt():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not (HA_ADDON and token):
        return None
    try:
        r = requests.get("http://supervisor/services/mqtt", headers={"Authorization": f"Bearer {token}"}, timeout=5)
        data = r.json().get("data") if r.ok else None
        return data if isinstance(data, dict) and data.get("host") else None
    except (requests.RequestException, ValueError):
        return None


def supervisor_slug():
    """The add-on's own slug (for example abcd1234_tilemark), for the link back from Home Assistant."""
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not (HA_ADDON and token):
        return ""
    try:
        r = requests.get("http://supervisor/addons/self/info", headers={"Authorization": f"Bearer {token}"}, timeout=5)
        data = r.json().get("data") if r.ok else None
        return str(data.get("slug") or "") if isinstance(data, dict) else ""
    except (requests.RequestException, ValueError):
        return ""


class MqttBridge:
    STATE_EVERY = 60  # seconds between checks for changed counts

    def __init__(self):
        self.client = None
        self.cfg = None
        self.status = {"state": "off", "error": "", "broker": "", "source": ""}
        self.last_payload = None
        self.wake = threading.Event()
        self._sup = (0, None)
        self._slug = None
        # announcing (on connect, in paho's thread) and taking away (on disconnect) never
        # run at the same time: otherwise a late "online" or state could land on topics
        # that were just cleared, leaving stale entities in Home Assistant
        self._io = threading.Lock()

    # -- configuration
    def node(self):
        n = get_setting("node_id")
        if not n:
            n = secrets.token_hex(3)
            set_setting("node_id", n)
        return n

    def new_node(self):
        """A fresh device ID, for an installation copied from another one (same database, same
        ID: Home Assistant would see the two as one device). The old entities are removed."""
        set_setting("node_id", secrets.token_hex(3))
        self.reload()

    def link(self):
        """Where this TileMark is opened: Home Assistant shows it as "Visit" on the device page."""
        if HA_ADDON:
            if self._slug is None:
                self._slug = supervisor_slug()
            return f"homeassistant://hassio/ingress/{self._slug}" if self._slug else ""
        return get_setting("mqtt_url", "")

    def default_name(self):
        if HA_ADDON:
            return "TileMark (Home Assistant)"
        host = urlparse(get_setting("mqtt_url", "")).hostname
        return f"TileMark ({host})" if host else "TileMark"

    def name(self):
        return get_setting("mqtt_name", "") or self.default_name()

    def enabled(self):
        return get_setting("mqtt_enabled", "on" if HA_ADDON else "off") == "on"

    def config(self):
        if not self.enabled():
            return None
        cfg = {"host": get_setting("mqtt_host", ""), "port": int(get_setting("mqtt_port", "1883") or 1883),
               "user": get_setting("mqtt_user", ""), "password": get_setting("mqtt_pass", ""),
               "tls": get_setting("mqtt_tls", "off") == "on", "prefix": get_setting("mqtt_prefix", "") or "homeassistant",
               "source": "settings"}
        cfg.update(node=self.node(), name=self.name(), link=self.link())  # a change republishes the device
        if not cfg["host"]:
            if time.time() - self._sup[0] > 600:  # ask the Supervisor at most every 10 minutes
                self._sup = (time.time(), supervisor_mqtt())
            svc = self._sup[1]
            if svc:
                cfg.update(host=svc["host"], port=int(svc.get("port") or 1883), user=svc.get("username") or "",
                           password=svc.get("password") or "", tls=bool(svc.get("ssl")), source="home-assistant")
        return cfg if cfg["host"] else {"missing": True, "node": cfg["node"]}

    # -- topics
    def base(self, node=None):
        return f"tilemark/{node or self.node()}"

    def device(self, node=None):
        node = node or self.node()
        dev = {"identifiers": [f"tilemark_{node}"], "name": self.name(), "manufacturer": "TileMark",
               "model": "Home Assistant app" if HA_ADDON else "Docker", "sw_version": APP_VERSION}
        if self.link():
            dev["configuration_url"] = self.link()
        return dev

    def discovery(self, prefix, node=None):
        node = node or self.node()
        base, dev = self.base(node), self.device(node)
        common = {"availability_topic": f"{base}/availability", "device": dev}
        state = f"{base}/state"
        return {
            f"{prefix}/sensor/{node}/links/config": {**common, "name": "Links", "unique_id": f"tilemark_{node}_links",
                "state_topic": state, "value_template": "{{ value_json.links }}", "unit_of_measurement": "links",
                "state_class": "measurement", "icon": "mdi:bookmark-multiple"},
            f"{prefix}/sensor/{node}/broken/config": {**common, "name": "Broken links", "unique_id": f"tilemark_{node}_broken",
                "state_topic": state, "value_template": "{{ value_json.broken }}", "unit_of_measurement": "links",
                "state_class": "measurement", "icon": "mdi:link-off"},
            f"{prefix}/sensor/{node}/last_check/config": {**common, "name": "Last link check", "unique_id": f"tilemark_{node}_last_check",
                "state_topic": state, "value_template": "{{ value_json.last_check }}", "device_class": "timestamp",
                "icon": "mdi:calendar-check"},
            f"{prefix}/sensor/{node}/last_backup/config": {**common, "name": "Last backup", "unique_id": f"tilemark_{node}_last_backup",
                "state_topic": state, "value_template": "{{ value_json.last_backup }}", "device_class": "timestamp",
                "icon": "mdi:backup-restore"},
            f"{prefix}/binary_sensor/{node}/backup_encryption/config": {**common, "name": "Backup encryption",
                "unique_id": f"tilemark_{node}_backup_encryption", "state_topic": state,
                "value_template": "{{ value_json.backup_encryption }}", "payload_on": "ON", "payload_off": "OFF",
                "icon": "mdi:shield-lock"},
            f"{prefix}/event/{node}/link_check/config": {**common, "name": "Link check", "unique_id": f"tilemark_{node}_link_check",
                "state_topic": f"{base}/event", "event_types": ["finished"], "icon": "mdi:link-variant"},
        }

    def stats(self):
        with db() as c:
            links, broken = c.execute("SELECT COUNT(*), COALESCE(SUM(broken), 0) FROM links").fetchone()
        last = int(get_setting("linkcheck_last", "0"))
        iso = lambda ts: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts else None
        # the newest daily backup of the whole installation (not the safety copies made before a restore)
        backup = max((b["made_at"] for b in all_backups() if b["kind"] == "daily"), default=0)
        return {"links": links, "broken": broken, "last_check": iso(last), "last_backup": iso(backup),
                "backup_encryption": "ON" if backup_encryption_on() else "OFF"}

    # -- connection
    def start(self):
        threading.Thread(target=self._run, daemon=True).start()

    def reload(self):
        self.wake.set()

    def connected(self):
        return bool(self.client and self.client.is_connected())

    def _run(self):
        while True:
            try:
                self.step()
            except Exception as e:  # never let MQTT trouble stop TileMark
                app.logger.exception("MQTT")
                self.status = {**self.status, "state": "error", "error": str(e)[:200]}
            self.wake.wait(self.STATE_EVERY)
            self.wake.clear()

    def step(self):
        """One round: (re)connect when the settings changed, otherwise publish changed counts."""
        cfg = self.config()
        if cfg != self.cfg:
            old = self.cfg or {}
            # entities go away when MQTT is turned off or the device gets a new ID
            self._disconnect(remove=bool(old) and (not cfg or cfg.get("node") != old.get("node")))
            self.cfg = cfg
            if not cfg:
                self.status = {"state": "off", "error": "", "broker": "", "source": ""}
            elif cfg.get("missing"):
                self.status = {"state": "error", "broker": "", "source": "",
                               "error": "No broker set" + (" and Home Assistant has no MQTT broker" if HA_ADDON else "") + "."}
            else:
                self._connect(cfg)
        elif self.connected():
            self.publish_state()

    def _connect(self, cfg):
        self.status = {"state": "connecting", "error": "", "broker": f"{cfg['host']}:{cfg['port']}", "source": cfg["source"]}
        cl = paho.Client(paho.CallbackAPIVersion.VERSION2, client_id=f"tilemark-{self.node()}-{secrets.token_hex(3)}")
        # the random part: two TileMarks never push each other off the broker, even with the same ID
        if cfg["user"]:
            cl.username_pw_set(cfg["user"], cfg["password"] or None)
        if cfg["tls"]:
            cl.tls_set()
        cl.will_set(f"{self.base(cfg['node'])}/availability", "offline", retain=True)
        cl.on_connect = self._on_connect
        cl.on_disconnect = self._on_disconnect
        cl.reconnect_delay_set(5, 300)
        self.client = cl
        cl.connect_async(cfg["host"], cfg["port"], keepalive=60)
        cl.loop_start()

    def _on_connect(self, client, userdata, flags, reason, properties=None):
        if reason.is_failure:
            self.status = {**self.status, "state": "error", "error": f"Broker refused the connection: {reason}"}
            return
        with self._io:
            if client is not self.client:  # replaced while connecting: say nothing on the old topics
                return
            self._announce(client)

    def _announce(self, client):
        for topic, payload in self.discovery(self.cfg["prefix"]).items():
            client.publish(topic, json.dumps(payload), qos=1, retain=True)
        client.publish(f"{self.base()}/availability", "online", qos=1, retain=True)
        self.last_payload = None
        self.publish_state()
        self.status = {**self.status, "state": "connected", "error": ""}

    def _on_disconnect(self, client, userdata, flags, reason, properties=None):
        if self.client is client and self.status.get("state") == "connected":
            self.status = {**self.status, "state": "connecting", "error": f"Connection lost ({reason}); retrying."}

    def _disconnect(self, remove=False):
        with self._io:
            cl, self.client = self.client, None
        if not cl:
            return
        try:  # QoS 1 and wait for each, so nothing is lost when the connection closes right after
            sent, old = [], (self.cfg or {}).get("node")
            if remove and self.cfg and not self.cfg.get("missing"):  # take the entities of the old ID away
                for topic in self.discovery(self.cfg["prefix"], old):
                    sent.append(cl.publish(topic, "", qos=1, retain=True))
                for topic in ("state", "event"):  # and their retained values
                    sent.append(cl.publish(f"{self.base(old)}/{topic}", "", qos=1, retain=True))
            sent.append(cl.publish(f"{self.base(old)}/availability", "offline", qos=1, retain=True))
            deadline = time.time() + 10  # one shared deadline: a slow broker gets time, a dead one costs 10 s at most
            for info in sent:
                info.wait_for_publish(max(0.1, deadline - time.time()))
        except Exception:
            pass
        cl.disconnect()
        cl.loop_stop()

    # -- messages
    def publish_state(self, force=False):
        if not self.connected():
            return
        payload = json.dumps(self.stats())
        if force or payload != self.last_payload:
            self.client.publish(f"{self.base()}/state", payload, retain=True)
            self.last_payload = payload

    def check_finished(self, checked, new_broken):
        if not self.connected():
            return
        st = self.stats()
        self.client.publish(f"{self.base()}/event", json.dumps(
            {"event_type": "finished", "checked": checked, "broken": st["broken"], "new_broken": new_broken}))
        self.publish_state(force=True)


mqtt = MqttBridge()


@app.route("/api/mqtt", methods=["GET", "POST"])
def mqtt_settings():
    """Admin: MQTT settings and connection status. An empty password keeps the stored one."""
    if request.method == "POST":
        d = request.get_json(force=True, silent=True) or {}
        if "enabled" in d:
            set_setting("mqtt_enabled", "on" if d["enabled"] else "off")
        for key, field, limit in (("host", "mqtt_host", 200), ("user", "mqtt_user", 200), ("prefix", "mqtt_prefix", 100)):
            if key in d:
                set_setting(field, str(d[key] or "").strip()[:limit])
        if "port" in d:
            try:
                port = int(d["port"] or 1883)
            except (TypeError, ValueError):
                return jsonify(error="The port must be a number."), 400
            if not 1 <= port <= 65535:
                return jsonify(error="The port must be between 1 and 65535."), 400
            set_setting("mqtt_port", str(port))
        if d.get("password"):
            set_setting("mqtt_pass", str(d["password"])[:500])
        if d.get("clear_password"):
            set_setting("mqtt_pass", "")
        if "tls" in d:
            set_setting("mqtt_tls", "on" if d["tls"] else "off")
        if "name" in d:
            set_setting("mqtt_name", str(d["name"] or "").strip()[:80])
        if not HA_ADDON and not request.headers.get("X-Ingress-Path"):
            set_setting("mqtt_url", request.host_url.rstrip("/"))  # the address the admin uses: the "Visit" link
        if d.get("new_id"):
            mqtt.new_node()
        mqtt.reload()
    return jsonify(enabled=mqtt.enabled(), host=get_setting("mqtt_host", ""), port=int(get_setting("mqtt_port", "1883") or 1883),
                   user=get_setting("mqtt_user", ""), has_password=bool(get_setting("mqtt_pass", "")),
                   tls=get_setting("mqtt_tls", "off") == "on", prefix=get_setting("mqtt_prefix", "") or "homeassistant",
                   addon=HA_ADDON, status=mqtt.status, node=mqtt.node(), name=get_setting("mqtt_name", ""),
                   default_name=mqtt.default_name(), link=mqtt.link())


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
    if HA_ADDON:  # inside Home Assistant the sidebar creates the first account; the code is only for the direct port
        print(f"\n{line}\n  TileMark has no account yet.\n  Open TileMark from the Home Assistant sidebar: the first person\n"
              f"  to open it becomes the admin. (Only if you set up TileMark through\n  its own port instead, it asks for this code: {setup_code()})\n{line}\n", flush=True)
        return
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
    uid, sid = session.get("uid"), session.get("sid")
    if not uid or not sid:
        return None
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        if not row or not secrets.compare_digest(str(session.get("ver", "")), row["ver"]):
            return None
        s_row = c.execute("SELECT last_seen FROM sessions WHERE id=? AND user_id=?", (sid, uid)).fetchone()
        if not s_row:  # signed out from another device
            return None
        if time.time() - s_row["last_seen"] > 300:
            c.execute("UPDATE sessions SET last_seen=? WHERE id=?", (int(time.time()), sid))
    return row


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


# Every sign-in is a row in "sessions", so "Your account" can list the devices that
# are signed in and sign any of them out. The cookie holds the row's id.
SESSION_DAYS = 31


def _visitor():
    return (request.headers.get("X-Forwarded-For", "").split(",")[-1].strip() or request.remote_addr or "")[:64]


def _sign_in(user):
    sid, now = secrets.token_hex(16), int(time.time())
    with db() as c:
        c.execute("DELETE FROM sessions WHERE last_seen < ?", (now - SESSION_DAYS * 86400,))
        c.execute("INSERT INTO sessions (id, user_id, created_at, last_seen, ua, ip) VALUES (?,?,?,?,?,?)",
                  (sid, user["id"], now, now, request.headers.get("User-Agent", "")[:250], _visitor()))
    session.clear()
    session["uid"] = user["id"]
    session["ver"] = user["ver"]
    session["sid"] = sid


def _end_other_sessions(uid, keep=""):
    with db() as c:
        c.execute("DELETE FROM sessions WHERE user_id=? AND id != ?", (uid, keep))


# ------------------------------------------------------- two-factor sign-in
# Optional per account: after the password, a 6-digit code from an authenticator app
# (TOTP, RFC 6238: HMAC-SHA1, 30 s steps), or one of ten single-use recovery codes.
# A code is accepted once only (the last used time step is stored). Not asked inside
# the Home Assistant sidebar, where Home Assistant has signed the person in already.
TOTP_STEP, TOTP_DIGITS = 30, 6
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _hotp(secret, counter):
    key = base64.b32decode(secret + "=" * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    off = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[off:off + 4])[0] & 0x7FFFFFFF) % 10 ** TOTP_DIGITS
    return str(code).zfill(TOTP_DIGITS)


def totp_check(secret, code, last_step=0, now=None):
    """The time step the code belongs to (one step of clock drift allowed either way),
    or None. Steps at or before last_step are refused, so a code works only once."""
    code = re.sub(r"\s", "", str(code or ""))
    if not secret or not re.fullmatch(rf"\d{{{TOTP_DIGITS}}}", code):
        return None
    step = int((time.time() if now is None else now) // TOTP_STEP)
    for s in (step - 1, step, step + 1):
        if s > last_step and hmac.compare_digest(_hotp(secret, s), code):
            return s
    return None


def _recovery_hash(code):
    return hashlib.sha256(re.sub(r"[^A-Z0-9]", "", str(code).upper()).encode()).hexdigest()


def _new_recovery_codes():
    codes = ["-".join("".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(5)) for _ in range(2)) for _ in range(10)]
    return codes, json.dumps([_recovery_hash(c) for c in codes])


def _use_recovery_code(c, user, code):
    """Consumes a recovery code. True if it was one of the user's unused codes."""
    try:
        left = json.loads(user["recovery"] or "[]")
    except ValueError:
        left = []
    h = _recovery_hash(code)
    if not re.sub(r"[^A-Z0-9]", "", str(code).upper()) or h not in left:
        return False
    left.remove(h)
    c.execute("UPDATE users SET recovery=? WHERE id=?", (json.dumps(left), user["id"]))
    return True


def _recovery_left(user):
    try:
        return len(json.loads(user["recovery"] or "[]"))
    except ValueError:
        return 0


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


OPEN_ENDPOINTS = {"login_page", "api_login", "api_login_totp", "auth_status", "api_setup", "icon", "save_page", "manifest",
                  "service_worker", "healthz", "i18n_script"}
KEY_ENDPOINTS = {"create_link", "list_groups"}  # all an API key may do: add links, read group names
ADMIN_ENDPOINTS = {"list_users", "create_user", "update_user", "delete_user", "save_settings", "list_full_backups",
                   "make_full_backup_now", "download_full_backup", "restore_full_backup_api", "mqtt_settings",
                   "backup_encryption"}


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


@app.get("/i18n.js")
def i18n_script():
    return send_from_directory(PAGES, "i18n.js", mimetype="text/javascript", max_age=0)


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
                   has_key=bool(u and u["api_key_hash"]), ha=bool(u) and via_ingress(), addon=HA_ADDON,
                   totp=bool(u and u["totp_secret"]), recovery_left=_recovery_left(u) if u else 0, version=APP_VERSION,
                   personal_key=bool(u and u["uk_pub"]))


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
        personal_key_set(con, uid, pw)
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
    keys_on_sign_in(row["id"], str(d.get("password", "")))  # the only moment the password is known
    if row["totp_secret"]:  # password right; the code comes next (5 minutes to enter it)
        session.clear()
        session["pending"] = {"uid": row["id"], "ver": row["ver"], "exp": int(time.time()) + 300,
                              "remember": bool(d.get("remember"))}
        return jsonify(totp=True)
    _sign_in(row)
    session.permanent = bool(d.get("remember"))  # otherwise the cookie ends with the browser session
    return jsonify(ok=True)


@app.post("/api/login/totp")
def api_login_totp():
    d = request.get_json(force=True, silent=True) or {}
    pend = session.get("pending") or {}
    if not pend or pend.get("exp", 0) < time.time():
        session.pop("pending", None)
        return jsonify(error="That took too long. Enter your password again.", restart=True), 401
    ip = _client()
    wait = _wait_seconds(ip)
    if wait:
        return jsonify(error=f"Too many attempts. Try again in {wait} seconds."), 429
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (pend["uid"],)).fetchone()
        if not row or row["ver"] != pend["ver"] or not row["totp_secret"]:
            session.pop("pending", None)
            return jsonify(error="Enter your password again.", restart=True), 401
        step = totp_check(row["totp_secret"], d.get("code"), row["totp_last"])
        if step is not None:
            c.execute("UPDATE users SET totp_last=? WHERE id=?", (step, row["id"]))
        ok = step is not None or _use_recovery_code(c, row, d.get("code"))
    _note_login(ip, ok)
    if not ok:
        return jsonify(error="That code is not right."), 401
    _sign_in(row)
    session.permanent = bool(pend.get("remember"))
    return jsonify(ok=True)


@app.post("/api/logout")
def api_logout():
    if session.get("sid"):
        with db() as c:
            c.execute("DELETE FROM sessions WHERE id=?", (session["sid"],))
    session.clear()
    return jsonify(ok=True)


@app.get("/api/sessions")
def list_sessions():
    with db() as c:
        rows = c.execute("SELECT id, created_at, last_seen, ua, ip FROM sessions WHERE user_id=? ORDER BY last_seen DESC",
                         (me(),)).fetchall()
    cur = session.get("sid") if not via_ingress() else None
    return jsonify(sessions=[dict(r) | {"current": r["id"] == cur} for r in rows])


@app.delete("/api/sessions/<sid>")
def end_session(sid):
    with db() as c:
        n = c.execute("DELETE FROM sessions WHERE id=? AND user_id=?", (sid, me())).rowcount
    return (jsonify(ok=True), 200) if n else (jsonify(error="Not found"), 404)


@app.post("/api/sessions/others")
def end_other_sessions():
    """Signs out every other device of this account (this one stays signed in)."""
    _end_other_sessions(me(), "" if via_ingress() else session.get("sid", ""))
    return jsonify(ok=True)


@app.post("/api/totp/setup")
def totp_setup():
    """Starts turning on two-factor sign-in: a new secret, shown as a QR code. It only
    takes effect after a code from the app has been confirmed (totp/enable)."""
    secret = base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")
    set_user_setting(me(), "totp_pending", json.dumps({"secret": secret, "exp": int(time.time()) + 900}))
    label = f"TileMark:{g.user['username']}"
    uri = f"otpauth://totp/{requests.utils.quote(label)}?secret={secret}&issuer=TileMark&digits={TOTP_DIGITS}&period={TOTP_STEP}"
    qr = segno.make(uri, error="m").svg_inline(scale=5, border=2, dark="#000", light="#fff")
    return jsonify(secret=secret, uri=uri, qr=qr)


@app.post("/api/totp/enable")
def totp_enable():
    d = request.get_json(force=True, silent=True) or {}
    try:
        pend = json.loads(get_user_setting(me(), "totp_pending", "{}"))
    except ValueError:
        pend = {}
    if not pend.get("secret") or pend.get("exp", 0) < time.time():
        return jsonify(error="Start again: the QR code has expired."), 400
    step = totp_check(pend["secret"], d.get("code"))
    if step is None:
        return jsonify(error="That code is not right. Check that the time on your phone is correct."), 400
    codes, hashes = _new_recovery_codes()
    with db() as c:
        c.execute("UPDATE users SET totp_secret=?, totp_last=?, recovery=? WHERE id=?", (pend["secret"], step, hashes, me()))
        c.execute("DELETE FROM user_settings WHERE user_id=? AND key='totp_pending'", (me(),))
    return jsonify(ok=True, recovery=codes)


def _password_or_ha(d):
    return via_ingress() or check_password_hash(g.user["pw_hash"], str(d.get("current_password", "")))


@app.delete("/api/totp")
def totp_disable():
    d = request.get_json(force=True, silent=True) or {}
    if not _password_or_ha(d):
        return jsonify(error="The current password is not correct."), 403
    with db() as c:
        c.execute("UPDATE users SET totp_secret='', totp_last=0, recovery='' WHERE id=?", (me(),))
    return jsonify(ok=True)


@app.post("/api/totp/recovery")
def totp_new_recovery():
    """New recovery codes; the old ones stop working."""
    d = request.get_json(force=True, silent=True) or {}
    if not g.user["totp_secret"]:
        return jsonify(error="Two-factor sign-in is not on."), 400
    if not _password_or_ha(d):
        return jsonify(error="The current password is not correct."), 403
    codes, hashes = _new_recovery_codes()
    with db() as c:
        c.execute("UPDATE users SET recovery=? WHERE id=?", (hashes, me()))
    return jsonify(ok=True, recovery=codes)


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
            # with the old password the personal key is only re-locked, so backups and access stay
            personal_key_set(c, me(), pw, None if via_ingress() else str(d.get("current_password", "")))
        row = c.execute("SELECT * FROM users WHERE id=?", (me(),)).fetchone()
    if not via_ingress():
        _sign_in(row)
        session.permanent = True
    if pw:  # a new password signs out every other device
        _end_other_sessions(me(), "" if via_ingress() else session.get("sid", ""))
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
        rows = c.execute("SELECT u.id, u.username, u.is_admin, u.created_at, u.totp_secret != '' AS totp, "
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
        personal_key_set(c, uid, pw)
    return jsonify(id=uid), 201


@app.patch("/api/users/<int:uid>")
def update_user(uid):
    """Rename, set a new password (signs that user out everywhere), change admin rights,
    or turn off their two-factor sign-in ("totp": false, for a lost phone)."""
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
        if pw:  # a new personal key: the old one was locked with a password nobody here knows
            c.execute("UPDATE users SET pw_hash=?, ver=? WHERE id=?", (_hash(pw), secrets.token_hex(16), uid))
            personal_key_set(c, uid, pw)
        if make is not None:
            c.execute("UPDATE users SET is_admin=? WHERE id=?", (make, uid))
            if not make:
                c.execute("DELETE FROM bk_grants WHERE user_id=?", (uid,))
        if d.get("totp") is False:
            c.execute("UPDATE users SET totp_secret='', totp_last=0, recovery='' WHERE id=?", (uid,))
        if pw:
            c.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
        fresh = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if uid == me() and pw and not via_ingress():  # keep the admin who changed their own password signed in here
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
             "thumb": ("s", "m", "l"), "open": ("new", "same"),
             "lang": ("", "en", "nl", "ar")}  # "" = follow the browser
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
    out = dict(groups=groups, links=links, check=check, prefs=_prefs(uid), version=APP_VERSION,
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
    if isinstance(d.get("dupok"), list):  # sets of links marked "not duplicates" in the Duplicates list
        prefs["dupok"] = [sorted({int(i) for i in grp if isinstance(i, int)})[:50]
                          for grp in d["dupok"][:500] if isinstance(grp, list)]
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
        dup = find_duplicate(c, uid, url_key(url))
        if dup and (not d.get("allow_duplicate") or dup["url"] == url):  # an identical address is never saved twice
            where = f' in "{dup["group_name"]}"' if dup["group_name"] else ""
            return jsonify(error=f"This page is already saved{where}: {dup['title'] or dup['url']}",
                           existing=_dup_info(dup)), 409
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
        if url != row["url"] and (find_duplicate(c, me(), url_key(url), link_id)
                                  or c.execute("SELECT 1 FROM links WHERE user_id=? AND url=?", (me(), url)).fetchone()):
            return jsonify(error="This page is already saved."), 409
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
            c.execute("UPDATE links SET url=?, ukey=?, final_key='', status='pending' WHERE id=?", (url, url_key(url), link_id))
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


# Import never drops a duplicate silently. Links that are new are added; links that
# are the same page as one already saved (or as one earlier in the same file) are
# returned in "duplicates", each next to the link it matches, so the person can
# download them, keep some as separate links, and discard the rest.
EXPORT_FORMAT = "tilemark-export"
MAX_REVIEW = 2000


def _parse_export(text):
    """A TileMark export file (JSON) as (groups, links), or None if the text is not one."""
    head = text.lstrip()[:200]
    if not head.startswith("{") or EXPORT_FORMAT not in head:
        return None
    try:
        d = json.loads(text)
    except ValueError:
        return None
    if not isinstance(d, dict) or d.get("format") != EXPORT_FORMAT:
        return None
    groups = [g for g in d.get("groups", []) if isinstance(g, dict)]
    links = [l for l in d.get("links", []) if isinstance(l, dict) and isinstance(l.get("url"), str)]
    return groups, links


@app.post("/api/import")
def import_links():
    text = request.form.get("text", "")
    f = request.files.get("file")
    if f:
        text += ("\n" if text else "") + f.read().decode("utf-8", errors="replace")
    export = _parse_export(text)
    if export:
        groups, rich = export
        items = [(l["url"], str(l.get("title") or ""), str(l.get("group") or ""), l)
                 for l in sorted(rich, key=lambda l: (l.get("position", 0) if isinstance(l.get("position"), int) else 0))]
    else:
        groups = []
        is_bookmarks = bool(re.search(r"<a\b[^>]*href", text, re.I))
        items = [(u, t, folder, None) for u, t, folder in (parse_bookmarks_html(text) if is_bookmarks else parse_plain(text))]
    added, skipped, new_ids, dups, uid = 0, 0, [], [], me()
    with db() as c:
        target = own_group(c, uid, request.form.get("group_id")) if request.form.get("group_id") else None
        colours = {str(g.get("name") or "").strip()[:60].lower(): g for g in groups}
        if target is None:  # an export's groups come first, in their order and colours (empty ones too)
            for g in sorted(groups, key=lambda g: g.get("position", 0) if isinstance(g.get("position"), int) else 0):
                name = str(g.get("name") or "").strip()[:60]
                if name and not c.execute("SELECT 1 FROM groups WHERE user_id=? AND name=?", (uid, name)).fetchone():
                    gid = get_or_create_group(c, uid, name)
                    if _color(g.get("color")):
                        c.execute("UPDATE groups SET color=? WHERE id=?", (g["color"], gid))
        seen = {}  # key -> the link earlier in this same import
        for raw, title, folder, extra in items:
            url = normalize_url(raw)
            if not url:
                skipped += 1
                continue
            key = url_key(url)
            match = find_duplicate(c, uid, key)
            earlier = seen.get(key)
            if match or earlier:
                if len(dups) < MAX_REVIEW:
                    dups.append({"url": url, "title": title.strip()[:300], "folder": folder, "note": str((extra or {}).get("note") or "")[:2000],
                                 "existing": {"id": None, "earlier": True, **earlier} if earlier else _dup_info(match),
                                 "same_address": (earlier["url"] if earlier else match["url"]) == url})
                continue
            gid = target
            if gid is None and folder:
                is_new = not c.execute("SELECT 1 FROM groups WHERE user_id=? AND name=?", (uid, folder.strip()[:60])).fetchone()
                gid = get_or_create_group(c, uid, folder)
                g = colours.get(folder.strip()[:60].lower())
                if is_new and g and _color(g.get("color")):
                    c.execute("UPDATE groups SET color=? WHERE id=?", (g["color"], gid))
            link_id = add_link(c, uid, url, gid, title, top=False)
            if link_id is None:
                skipped += 1
                continue
            seen[key] = {"url": url, "title": title.strip()[:300], "group": folder}
            if extra:
                _apply_export_fields(c, link_id, extra)
            added += 1
            new_ids.append(link_id)
    for link_id in new_ids:
        queue(link_id)
    return jsonify(added=added, skipped=skipped, duplicates=dups)


def _apply_export_fields(c, link_id, d):
    """Notes, favourite, dates, own title and own picture from a TileMark export."""
    def num(v):
        return v if isinstance(v, int) and v >= 0 else 0
    c.execute("UPDATE links SET description=?, note=?, pinned=?, created_at=COALESCE(NULLIF(?, 0), created_at), "
              "opened_at=?, custom_title=? WHERE id=?",
              (str(d.get("description") or "")[:500], str(d.get("note") or "")[:2000], 1 if d.get("pinned") else 0,
               num(d.get("created_at")), num(d.get("opened_at")), 1 if d.get("custom_title") and d.get("title") else 0, link_id))
    pic = d.get("picture")
    if isinstance(pic, str) and pic:
        try:
            name = _save_thumb(link_id, base64.b64decode(pic, validate=True), "image")
        except (ValueError, TypeError):
            name = None
        if name:
            c.execute("UPDATE links SET thumb=?, thumb_kind='image', custom_thumb=1 WHERE id=?", (name, link_id))


@app.post("/api/duplicates/merge")
def merge_duplicates():
    """Keep one link of a set of duplicates and remove the others. With "merge", the
    kept link takes over what the others had: notes, favourite, own title and own
    picture (if it has none), a group (if it has none), the earliest saved date."""
    d = request.get_json(force=True, silent=True) or {}
    keep = d.get("keep")
    remove = [i for i in _ids({"ids": d.get("remove", [])}) if i != keep]
    with db() as c:
        k = own_link(c, keep) if isinstance(keep, int) else None
        others = [own_link(c, i) for i in remove]
        if not k or not others or not all(others):
            return jsonify(error="Those links were not found."), 404
        moved = None
        if d.get("merge"):
            notes = [n for n in dict.fromkeys(x["note"].strip() for x in [k] + others) if n]
            upd = {"note": "\n\n".join(notes)[:2000], "pinned": max(x["pinned"] for x in [k] + others),
                   "created_at": min(x["created_at"] for x in [k] + others), "opened_at": max(x["opened_at"] for x in [k] + others)}
            if not k["custom_title"]:
                t = next((x for x in others if x["custom_title"]), None)
                if t:
                    upd.update(title=t["title"], custom_title=1)
            if not k["custom_thumb"]:
                t = next((x for x in others if x["custom_thumb"] and x["thumb"]), None)
                if t:
                    moved = t["thumb"]
                    upd.update(thumb=t["thumb"], thumb_kind="image", custom_thumb=1)
            if k["group_id"] is None:
                g = next((x["group_id"] for x in others if x["group_id"] is not None), None)
                if g is not None:
                    upd["group_id"] = g
            c.execute(f"UPDATE links SET {', '.join(f'{col}=?' for col in upd)} WHERE id=?", [*upd.values(), keep])
        thumbs = [x["thumb"] for x in others if x["thumb"] and x["thumb"] != moved]
        if moved and k["thumb"] and k["thumb"] != moved:
            thumbs.append(k["thumb"])
        c.execute(f"DELETE FROM links WHERE user_id=? AND id IN ({','.join('?' * len(remove))})", [me()] + remove)
    for name in thumbs:
        _remove_thumb(name)
    return jsonify(ok=True, removed=len(remove))


@app.get("/api/export")
def export_links():
    """Standard bookmarks file (re-importable here and in any browser), or with
    ?format=json a TileMark file with everything: notes, favourites, order, colours,
    dates and own pictures (fetched thumbnails are left out; they come back by themselves)."""
    if request.args.get("format") == "json":
        return _export_json()
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


def _export_json():
    with db() as c:
        groups = c.execute("SELECT id, name, color, position FROM groups WHERE user_id=? ORDER BY position, id", (me(),)).fetchall()
        links = c.execute("SELECT * FROM links WHERE user_id=? ORDER BY position, id DESC", (me(),)).fetchall()
    names = {g["id"]: g["name"] for g in groups}
    out_links = []
    for pos, l in enumerate(links):
        item = {"url": l["url"], "title": l["title"], "custom_title": bool(l["custom_title"]), "description": l["description"],
                "note": l["note"], "pinned": bool(l["pinned"]), "group": names.get(l["group_id"], ""), "position": pos,
                "created_at": l["created_at"], "opened_at": l["opened_at"]}
        if l["custom_thumb"] and l["thumb"]:
            try:
                with open(os.path.join(THUMB_DIR, os.path.basename(l["thumb"])), "rb") as f:
                    item["picture"] = base64.b64encode(f.read()).decode()
            except OSError:
                pass
        out_links.append(item)
    body = json.dumps({"format": EXPORT_FORMAT, "version": 1, "exported_at": int(time.time()),
                       "groups": [{"name": g["name"], "color": g["color"], "position": i} for i, g in enumerate(groups)],
                       "links": out_links}, ensure_ascii=False, indent=1)
    return Response(body, mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=tilemark-export-" + time.strftime("%Y-%m-%d") + ".json"})


# ---------------------------------------------------------------- encryption keys
# Backups are encrypted without an extra password to remember:
#
# * Every account with a password has a personal key pair (X25519). The private
#   half is stored locked with the login password (scrypt + AES-GCM), so only that
#   password opens it. Personal backups are sealed to the public half.
# * When an admin turns on encrypted backups, the installation gets a backup key
#   pair. Daily backups and safety copies are sealed to its public half, so they
#   can be made at night with nobody signed in. The private half is stored only
#   sealed, once per admin to that admin's personal key ("grants"), and once
#   locked with a recovery key shown a single time.
# * Each backup file carries those locked copies in its header, so it opens on a
#   brand-new installation with an admin's password from that day, or the
#   recovery key.
# * A password changed by its owner re-locks the same personal key, so nothing is
#   lost. A password reset by someone else (admin, reset-login) gives a new
#   personal key; access to backups comes back the next time an admin with access
#   signs in, or with the recovery key.
SEAL_INFO = b"tilemark-seal-1"
KEY_AAD = b"tilemark-key-1"
RECOVERY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I: easy to copy by hand


def _b64(b):
    return base64.b64encode(b).decode("ascii")


def _unb64(s):
    return base64.b64decode(s.encode("ascii")) if s else b""


def _raw_priv(k):
    return k.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())


def _raw_pub(k):
    return k.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def _pub_of(priv_raw):
    return _raw_pub(X25519PrivateKey.from_private_bytes(priv_raw))


def _lock(secret, password):
    """secret locked with a password: 16-byte salt + 12-byte nonce + AES-GCM."""
    salt, nonce = os.urandom(16), os.urandom(12)
    return salt + nonce + AESGCM(_key(password, salt)).encrypt(nonce, secret, KEY_AAD)


def _unlock(blob, password):
    if len(blob) < 29 or not password:
        return None
    try:
        return AESGCM(_key(password, blob[:16])).decrypt(blob[16:28], blob[28:], KEY_AAD)
    except InvalidTag:
        return None


def _seal(data, pub_raw, aad=b""):
    """data sealed to a public key: 32-byte one-time public key + 12-byte nonce + AES-GCM."""
    eph = X25519PrivateKey.generate()
    eph_pub = _raw_pub(eph)
    shared = eph.exchange(X25519PublicKey.from_public_bytes(pub_raw))
    key = HKDF(hashes.SHA256(), 32, salt=None, info=SEAL_INFO + eph_pub + pub_raw).derive(shared)
    nonce = os.urandom(12)
    return eph_pub + nonce + AESGCM(key).encrypt(nonce, data, aad)


def _open(blob, priv_raw, aad=b""):
    """The other side of _seal. Raises InvalidTag when the key or the data is wrong."""
    if len(blob) < 44:
        raise InvalidTag()
    priv = X25519PrivateKey.from_private_bytes(priv_raw)
    shared = priv.exchange(X25519PublicKey.from_public_bytes(blob[:32]))
    key = HKDF(hashes.SHA256(), 32, salt=None, info=SEAL_INFO + blob[:32] + _raw_pub(priv)).derive(shared)
    return AESGCM(key).decrypt(blob[32:44], blob[44:], aad)


def new_recovery_key():
    return "-".join("".join(secrets.choice(RECOVERY_ALPHABET) for _ in range(5)) for _ in range(5))


def _recovery_norm(text):
    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper())


# -- personal keys
def personal_key_set(c, uid, password, old_password=None):
    """Give this account a personal key locked with `password`. With the old password
    the existing key is kept and only re-locked, so backups and grants stay valid."""
    row = c.execute("SELECT uk_pub, uk_priv FROM users WHERE id=?", (uid,)).fetchone()
    priv = _unlock(_unb64(row["uk_priv"]), old_password) if (row and row["uk_priv"] and old_password) else None
    if priv is None:
        priv = _raw_priv(X25519PrivateKey.generate())
    c.execute("UPDATE users SET uk_pub=?, uk_priv=? WHERE id=?", (_b64(_pub_of(priv)), _b64(_lock(priv, password)), uid))
    return priv


def personal_key_open(row, password):
    return _unlock(_unb64(row["uk_priv"]), password) if row["uk_priv"] else None


# -- the installation's backup key
def backup_encryption_on():
    return get_setting("bk_on", "off") == "on" and bool(get_setting("bk_pub", ""))


def _grant_valid(c, row):
    g_ = c.execute("SELECT * FROM bk_grants WHERE user_id=?", (row["id"],)).fetchone()
    return g_ if (g_ and row["uk_pub"] and g_["uk_pub"] == row["uk_pub"]) else None


def backup_key_with_password(c, row, password):
    """The backup key's private half, opened with this admin's password (or None)."""
    grant = _grant_valid(c, row)
    priv = personal_key_open(row, password) if grant else None
    if not priv:
        return None
    try:
        bk = _open(_unb64(grant["sealed"]), priv)
    except InvalidTag:
        return None
    return bk if _b64(_pub_of(bk)) == get_setting("bk_pub", "") else None


def backup_key_with_recovery(recovery, blob=None, pub=None):
    bk = _unlock(blob if blob is not None else _unb64(get_setting("bk_recovery", "")), _recovery_norm(recovery))
    return bk if bk and _b64(_pub_of(bk)) == (pub or get_setting("bk_pub", "")) else None


def share_backup_key(c, bk):
    """Seal the backup key to every admin who has a personal key but no valid grant;
    take it away from accounts that are no longer admin."""
    c.execute("DELETE FROM bk_grants WHERE user_id NOT IN (SELECT id FROM users WHERE is_admin=1)")
    n = 0
    for row in c.execute("SELECT id, uk_pub FROM users WHERE is_admin=1 AND uk_pub != ''").fetchall():
        if not _grant_valid(c, row):
            c.execute("INSERT INTO bk_grants (user_id, uk_pub, sealed) VALUES (?,?,?) ON CONFLICT(user_id) "
                      "DO UPDATE SET uk_pub=excluded.uk_pub, sealed=excluded.sealed",
                      (row["id"], row["uk_pub"], _b64(_seal(bk, _unb64(row["uk_pub"])))))
            n += 1
    return n


def keys_on_sign_in(uid, password):
    """Called whenever a password is known to be right: makes sure the account has a
    personal key, and lets an admin with access pass access on to other admins."""
    try:
        with db() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if not row:
                return
            if not personal_key_open(row, password):  # none yet (made before 2.4), or reset by someone else
                personal_key_set(c, uid, password)
                row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if row["is_admin"] and backup_encryption_on():
                bk = backup_key_with_password(c, row, password)
                if bk:
                    share_backup_key(c, bk)
    except Exception:  # never let key upkeep stop anyone from signing in
        app.logger.exception("keys on sign-in")


# ------------------------------------------------------- backup and restore
# A backup holds one user's links, groups and thumbnails: a zip with a small
# database (tables "groups" and "links") and the thumbnails. With a password it is
# wrapped as: MAGIC + 16-byte salt + 12-byte nonce + AES-256-GCM(zip), key =
# scrypt(password). Accounts, passwords and API keys are never in a backup.
# Backups made under the app's previous name use LEGACY_MAGIC and a database named
# LEGACY_DB in the zip; they restore exactly like new ones.
MAGIC = b"TILEMARK-BACKUP-1\n"
# Since 2.4 a backup is by default sealed to the account's personal key instead:
# MAGIC2 + 4-byte header length + header (JSON: the personal key's public half and
# its private half, locked with the login password of that day) + the sealed zip.
# It opens with that password, or with today's password when it was changed since.
MAGIC2 = b"TILEMARK-BACKUP-2\n"
BACKUP_DB = "tilemark.db"
LEGACY_MAGIC = b"LINK" + b"BOARD-BACKUP-1\n"
LEGACY_DB = "link" + "board.db"
MAX_BACKUP_DB = 512 * 1024 * 1024


def _key(password, salt):
    return Scrypt(salt=salt, length=32, n=2 ** 15, r=8, p=1).derive(password.encode("utf-8"))


def make_backup(uid, password="", personal=True):
    """password: lock with that password (format 1). Otherwise, with personal=True and
    a personal key, seal to it (format 2). Otherwise a plain zip."""
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
        return MAGIC + salt + nonce + AESGCM(_key(password, salt)).encrypt(nonce, data, MAGIC)
    with db() as c:
        row = c.execute("SELECT uk_pub, uk_priv FROM users WHERE id=?", (uid,)).fetchone()
    if personal and row and row["uk_pub"]:
        header = json.dumps({"v": 2, "uk_pub": row["uk_pub"], "uk_priv": row["uk_priv"]}).encode("utf-8")
        return MAGIC2 + struct.pack(">I", len(header)) + header + _seal(data, _unb64(row["uk_pub"]), MAGIC2 + header)
    return data


class RestoreError(Exception):
    pass


def _open_personal_backup(uid, data, password):
    try:
        n = struct.unpack(">I", data[len(MAGIC2):len(MAGIC2) + 4])[0]
        header_raw = data[len(MAGIC2) + 4:len(MAGIC2) + 4 + n]
        header, body = json.loads(header_raw), data[len(MAGIC2) + 4 + n:]
    except (struct.error, ValueError):
        raise RestoreError("This is not a TileMark backup file.")
    if not password:
        raise RestoreError("This backup is protected. Enter its password.")
    uk = _unlock(_unb64(header.get("uk_priv", "")), password)  # the password of the day it was made
    if not uk:
        with db() as c:  # or today's, when the owner changed it since (the key stayed the same)
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
        uk = personal_key_open(row, password) if row and row["uk_pub"] == header.get("uk_pub") else None
    if not uk:
        raise RestoreError("Wrong password. Use your password from the day of the backup, or today's.")
    try:
        return _open(body, uk, MAGIC2 + header_raw)
    except InvalidTag:
        raise RestoreError("Wrong password, or the backup file is damaged.")


def restore_backup(uid, data, password=""):
    """Replace this user's links and groups with the ones in the backup. Ids are
    given anew (other users' ids may be taken), so groups and pictures are mapped."""
    if data.startswith(MAGIC2):
        data = _open_personal_backup(uid, data, password)
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
        return sorted(n for n in os.listdir(BACKUP_DIR) if re.fullmatch(r"tilemark-\d{4}-\d{2}-\d{2}\.(zip|tmk)", n))
    except OSError:
        return []


SAFETY_PREFIX, KEEP_SAFETY = "tilemark-before-restore-", 3
KEEP_ON_RESTORE = ("node_id", "secret_key", "mqtt_enabled", "mqtt_host", "mqtt_port", "mqtt_user", "mqtt_pass", "mqtt_tls",
                   "mqtt_prefix", "mqtt_name", "mqtt_url")


def daily_backup():
    final = _write_full_backup(time.strftime("tilemark-%Y-%m-%d"))
    for old in list_backups()[:-KEEP_BACKUPS]:
        try:
            os.remove(os.path.join(BACKUP_DIR, old))
        except OSError:
            pass
    set_setting("backup_last", str(int(time.time())))
    try:
        mqtt.publish_state()  # Home Assistant's "Last backup" follows right away
    except Exception:
        app.logger.exception("MQTT")
    return final


# With encryption on, a backup file is: MAGIC_FULL + 4-byte header length + header
# (JSON: the backup key's public half, and its private half locked per admin and
# with the recovery key) + the zip sealed to the backup key, with MAGIC_FULL and
# the header as associated data, so neither can be changed unnoticed.
MAGIC_FULL = b"TILEMARK-FULL-1\n"


def _full_header():
    with db() as c:
        keys = [{"uk_priv": r["uk_priv"], "sealed": r["sealed"]} for r in c.execute(
            "SELECT u.uk_priv, g.sealed FROM bk_grants g JOIN users u ON u.id = g.user_id "
            "WHERE u.is_admin = 1 AND u.uk_pub = g.uk_pub AND u.uk_priv != ''")]
    return json.dumps({"v": 1, "bk_pub": get_setting("bk_pub", ""), "keys": keys,
                       "recovery": get_setting("bk_recovery", "")}).encode("utf-8")


def _write_full_backup(base):
    """Write a backup of the whole installation: base + ".tmk" when encryption is on, else ".zip"."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    encrypt = backup_encryption_on()
    final = os.path.join(BACKUP_DIR, base + (".tmk" if encrypt else ".zip"))
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
    if encrypt:
        with open(part, "rb") as f:
            plain = f.read()
        header = _full_header()
        with open(part, "wb") as f:
            f.write(MAGIC_FULL + struct.pack(">I", len(header)) + header
                    + _seal(plain, _unb64(get_setting("bk_pub", "")), MAGIC_FULL + header))
    os.replace(part, final)
    return final


def read_full_backup(path, secret="", uid=None):
    """The zip inside a backup of the whole installation. An encrypted one opens with
    the password of an admin (the current one, or theirs on the day of the backup) or
    with the recovery key."""
    with open(path, "rb") as f:
        data = f.read()
    if not data.startswith(MAGIC_FULL):
        return data
    try:
        n = struct.unpack(">I", data[len(MAGIC_FULL):len(MAGIC_FULL) + 4])[0]
        header_raw = data[len(MAGIC_FULL) + 4:len(MAGIC_FULL) + 4 + n]
        header, body = json.loads(header_raw), data[len(MAGIC_FULL) + 4 + n:]
        pub = header["bk_pub"]
    except (struct.error, ValueError, KeyError, TypeError):
        raise FullRestoreError("That file is not a TileMark backup.")
    if not secret:
        raise FullRestoreError("This backup is encrypted. Enter your password or the recovery key.")
    fits = lambda k: k if (k and _b64(_pub_of(k)) == pub) else None
    bk = None
    if uid:  # the current admin's password, through their access today
        with db() as c:
            row = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
            if row and check_password_hash(row["pw_hash"], secret):
                grant = _grant_valid(c, row)
                uk = personal_key_open(row, secret) if grant else None
                try:
                    bk = fits(_open(_unb64(grant["sealed"]), uk)) if uk else None
                except InvalidTag:
                    bk = None
    for k in header.get("keys", []) if not bk else []:  # an admin's password on the day of the backup
        uk = _unlock(_unb64(k.get("uk_priv", "")), secret)
        if uk:
            try:
                bk = fits(_open(_unb64(k.get("sealed", "")), uk))
            except InvalidTag:
                bk = None
            if bk:
                break
    if not bk:
        bk = backup_key_with_recovery(secret, _unb64(header.get("recovery", "")), pub)
    if not bk:
        raise FullRestoreError("That password or recovery key does not open this backup.")
    try:
        return _open(body, bk, MAGIC_FULL + header_raw)
    except InvalidTag:
        raise FullRestoreError("The backup file is damaged.")


def all_backups():
    """Daily backups and the safety copies made before a restore, newest first."""
    out = []
    try:
        names = os.listdir(BACKUP_DIR)
    except OSError:
        names = []
    for n in names:
        m = re.fullmatch(r"tilemark-(\d{4}-\d{2}-\d{2})\.(zip|tmk)", n) or re.fullmatch(
            re.escape(SAFETY_PREFIX) + r"(\d{4}-\d{2}-\d{2})-\d{6}\.(zip|tmk)", n)
        if m:
            st = os.stat(os.path.join(BACKUP_DIR, n))
            out.append({"name": n, "date": m.group(1), "size": st.st_size, "made_at": int(st.st_mtime),
                        "kind": "safety" if n.startswith(SAFETY_PREFIX) else "daily", "encrypted": n.endswith(".tmk")})
    return sorted(out, key=lambda b: b["made_at"], reverse=True)


class FullRestoreError(Exception):
    pass


def restore_full_backup(name, secret="", uid=None):
    """Replace the whole installation (every account) with a daily backup. A safety
    copy of the current state is made first, so a restore can itself be undone."""
    entry = next((b for b in all_backups() if b["name"] == name), None)
    if not entry:
        raise FullRestoreError("That backup was not found.")
    path = os.path.join(BACKUP_DIR, name)
    with tempfile.TemporaryDirectory() as tmp:
        try:
            z = zipfile.ZipFile(io.BytesIO(read_full_backup(path, secret, uid)))
            info = z.getinfo(BACKUP_DB)
        except (zipfile.BadZipFile, KeyError, OSError):
            raise FullRestoreError("That file is not a TileMark backup.")
        if info.file_size > MAX_BACKUP_DB:
            raise FullRestoreError("The backup's database is too large.")
        snap = os.path.join(tmp, "restore.db")
        with open(snap, "wb") as f:
            f.write(z.read(info))
        try:
            chk = sqlite3.connect(snap)
            ok = chk.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            users = chk.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            links = chk.execute("SELECT COUNT(*) FROM links").fetchone()[0]
            chk.close()
        except sqlite3.Error:
            raise FullRestoreError("The backup's database cannot be read.")
        if not ok or users < 1:  # a backup without accounts would lock everyone out
            raise FullRestoreError("The backup's database is damaged or has no accounts.")
        safety = _write_full_backup(SAFETY_PREFIX + time.strftime("%Y-%m-%d-%H%M%S"))
        for old in [b["name"] for b in all_backups() if b["kind"] == "safety"][KEEP_SAFETY:]:
            try:
                os.remove(os.path.join(BACKUP_DIR, old))
            except OSError:
                pass
        with db() as c:  # how this installation connects (MQTT, its device id in HA, its key) stays as it is now
            keep = c.execute(f"SELECT key, value FROM settings WHERE key IN ({','.join('?' * len(KEEP_ON_RESTORE))})",
                             KEEP_ON_RESTORE).fetchall()
        src, dst = sqlite3.connect(snap), sqlite3.connect(DB_PATH, timeout=60)
        try:
            src.backup(dst)  # replaces the live database in one step, while the app keeps running
        finally:
            src.close()
            dst.close()
        for member in z.infolist():
            fname = os.path.basename(member.filename)
            if (member.filename.startswith("thumbs/") and re.fullmatch(r"[\w.-]+\.(webp|png)", fname)
                    and member.file_size <= 20_000_000 and not os.path.exists(os.path.join(THUMB_DIR, fname))):
                with open(os.path.join(THUMB_DIR, fname), "wb") as f:
                    f.write(z.read(member))
    init_db()  # an older backup gets today's columns
    pending = []
    with db() as c:
        for r in keep:
            c.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                      (r["key"], r["value"]))
        for r in c.execute("SELECT id, thumb, custom_thumb FROM links WHERE thumb != ''").fetchall():
            if not os.path.isfile(os.path.join(THUMB_DIR, os.path.basename(r["thumb"]))):
                c.execute("UPDATE links SET thumb='', thumb_kind='', custom_thumb=0, status='pending' WHERE id=?", (r["id"],))
                pending.append(r["id"])
        c.execute("DELETE FROM sessions")  # everyone signs in again, with the restored accounts
    for link_id in pending:
        queue(link_id)
    mqtt.last_payload = None  # publish the restored counts
    mqtt.reload()
    return {"links": links, "users": users, "safety": os.path.basename(safety)}


def _encryption_status():
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (me(),)).fetchone()
        access = bool(_grant_valid(c, row))
        admins_without = c.execute("SELECT COUNT(*) FROM users u WHERE is_admin=1 AND NOT EXISTS "
                                   "(SELECT 1 FROM bk_grants g WHERE g.user_id=u.id AND g.uk_pub=u.uk_pub AND u.uk_pub != '')").fetchone()[0]
    return {"on": backup_encryption_on(), "access": access, "personal_key": bool(row["uk_pub"]),
            "admins_without_access": admins_without}


@app.get("/api/backups")
def list_full_backups():
    return jsonify(backups=all_backups(), daily=daily_backup_on(), encryption=_encryption_status())


@app.post("/api/backups")
def make_full_backup_now():
    """Make today's daily backup now (replaces an earlier one from today)."""
    daily_backup()
    return jsonify(ok=True, backups=all_backups())


@app.get("/api/backups/<name>")
def download_full_backup(name):
    if not any(b["name"] == name for b in all_backups()):
        return jsonify(error="Not found"), 404
    return send_from_directory(BACKUP_DIR, name, as_attachment=True, max_age=0)


@app.post("/api/backups/restore")
def restore_full_backup_api():
    d = request.get_json(force=True, silent=True) or {}
    name = str(d.get("name", ""))
    entry = next((b for b in all_backups() if b["name"] == name), None)
    if not entry:
        return jsonify(error="That backup was not found."), 404
    if str(d.get("confirm", "")).strip() != entry["date"]:
        return jsonify(error=f"To confirm, type the date of the backup: {entry['date']}"), 400
    try:
        result = restore_full_backup(name, str(d.get("secret", "")), me())
    except FullRestoreError as e:
        return jsonify(error=str(e), need_secret=entry["encrypted"]), 400
    session.clear()
    return jsonify(ok=True, **result)


@app.post("/api/backups/encryption")
def backup_encryption():
    """Admin: turn encryption of the whole-installation backups on or off, make a new
    recovery key, or get access again with the recovery key."""
    d = request.get_json(force=True, silent=True) or {}
    action, secret = d.get("action"), str(d.get("password", ""))
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE id=?", (me(),)).fetchone()
    password_ok = via_ingress() or check_password_hash(row["pw_hash"], secret)
    if action == "on":
        if not password_ok:
            return jsonify(error="The current password is not correct."), 403
        if backup_encryption_on():
            return jsonify(error="Backups are already encrypted."), 409
        bk, recovery = _raw_priv(X25519PrivateKey.generate()), new_recovery_key()
        with db() as c:
            for key, value in (("bk_pub", _b64(_pub_of(bk))), ("bk_recovery", _b64(_lock(bk, _recovery_norm(recovery)))),
                               ("bk_on", "on")):
                c.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                          (key, value))
            c.execute("DELETE FROM bk_grants")
            share_backup_key(c, bk)
        if daily_backup_on():
            daily_backup()  # the first encrypted one, before the old ones go
        removed = 0
        for b in all_backups():  # the unencrypted ones: confirmed by the admin before turning this on
            if not b["encrypted"]:
                try:
                    os.remove(os.path.join(BACKUP_DIR, b["name"]))
                    removed += 1
                except OSError:
                    pass
        return jsonify(ok=True, recovery=recovery, removed=removed, encryption=_encryption_status(), backups=all_backups())
    if action == "off":
        if not password_ok:
            return jsonify(error="The current password is not correct."), 403
        with db() as c:
            c.execute("DELETE FROM settings WHERE key IN ('bk_pub', 'bk_recovery', 'bk_on')")
            c.execute("DELETE FROM bk_grants")
        return jsonify(ok=True, encryption=_encryption_status())
    if action in ("recovery", "unlock"):
        if not backup_encryption_on():
            return jsonify(error="Backups are not encrypted."), 400
        with db() as c:
            bk = (backup_key_with_password(c, row, secret) if check_password_hash(row["pw_hash"], secret) else None) \
                or backup_key_with_recovery(secret)
            if not bk:
                return jsonify(error="That password or recovery key is not right."), 403
            share_backup_key(c, bk)  # you (and any admin without access) can open the backups again
            if action == "recovery":
                recovery = new_recovery_key()
                c.execute("UPDATE settings SET value=? WHERE key='bk_recovery'", (_b64(_lock(bk, _recovery_norm(recovery))),))
                return jsonify(ok=True, recovery=recovery, encryption=_encryption_status())
        return jsonify(ok=True, encryption=_encryption_status())
    return jsonify(error="Nothing to do."), 400


@app.post("/api/backup")
def api_backup():
    d = request.get_json(force=True, silent=True) or {}
    password, plain = str(d.get("password", "")), bool(d.get("plain"))
    if not password and not plain and not g.user["uk_pub"]:
        login = str(d.get("login_password", ""))  # an account from before 2.4: its key is made once, now
        if via_ingress() or not check_password_hash(g.user["pw_hash"], login):
            return jsonify(error="Enter your password once to set up encrypted backups.", need_password=not via_ingress(),
                           no_key=True), 428
        with db() as c:
            personal_key_set(c, me(), login)
    data = make_backup(me(), password, personal=not plain)
    encrypted = data.startswith(MAGIC) or data.startswith(MAGIC2)
    name = "tilemark-backup-" + time.strftime("%Y-%m-%d") + (".tmk" if encrypted else ".zip")
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
        pw = secrets.token_urlsafe(12)  # also turns off two-factor sign-in: a lost phone never locks anyone out
        c.execute("UPDATE users SET pw_hash=?, ver=?, totp_secret='', totp_last=0, recovery='' WHERE id=?",
                  (_hash(pw), secrets.token_hex(16), row["id"]))
        personal_key_set(c, row["id"], pw)
        c.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
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
    mqtt.start()
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
