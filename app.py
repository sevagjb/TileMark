"""LinkBoard - a tiny self-hosted page for your links, with thumbnails and groups."""
import html
import ipaddress
import io
import os
import re
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from flask import Flask, Response, jsonify, request, send_from_directory
from PIL import Image

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
COLORS = ["#4c8bf5", "#e5534b", "#e0a31b", "#3fa55a", "#d6589f", "#8e6ad8", "#2aa7b8", "#e8793a", "#7d8590"]

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024
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
    n = c.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
    return c.execute("INSERT INTO groups (name, color) VALUES (?, ?)",
                     (name, COLORS[n % len(COLORS)])).lastrowid


def add_link(c, url, group_id=None, title=""):
    """Insert a link. Returns the new id, or None if it already exists."""
    title = (title or "").strip()[:300]
    try:
        return c.execute(
            "INSERT INTO links (url, title, group_id, custom_title, created_at) VALUES (?,?,?,?,?)",
            (url, title, group_id, 0, int(time.time()))).lastrowid
    except sqlite3.IntegrityError:
        return None


# ------------------------------------------------------- metadata fetching
def _download(url, limit):
    r = requests.get(url, headers=UA, timeout=12, stream=True)
    r.raise_for_status()
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


def fetch_meta(link_id):
    with db() as c:
        row = c.execute("SELECT * FROM links WHERE id = ?", (link_id,)).fetchone()
    if not row:
        return
    url = row["url"]
    title, desc, status = "", "", "ok"
    images, icons = [], []
    try:
        data, ctype, final = _download(url, 2_000_000)
        if ctype.startswith("image/"):
            images.append(final)
        else:
            soup = BeautifulSoup(data, "html.parser")
            title = _meta(soup, "og:title", "twitter:title") or (soup.title.get_text(strip=True) if soup.title else "")
            desc = _meta(soup, "og:description", "twitter:description", "description")
            for key in ("og:image:secure_url", "og:image", "twitter:image", "twitter:image:src"):
                v = _meta(soup, key)
                if v:
                    images.append(urljoin(final, v))
            for tag in soup.find_all("link", href=True):
                rel = " ".join(tag.get("rel") or []).lower()
                if "apple-touch-icon" in rel:
                    icons.insert(0, urljoin(final, tag["href"]))
                elif "icon" in rel:
                    icons.append(urljoin(final, tag["href"]))
        icons.append(urljoin(final, "/favicon.ico"))
    except Exception:
        status = "error"
        icons.append(urljoin(url, "/favicon.ico"))

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


# --------------------------------------------------------------------- api
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/thumbs/<path:name>")
def thumbs(name):
    return send_from_directory(THUMB_DIR, name, max_age=31536000)


@app.get("/api/state")
def state():
    with db() as c:
        groups = [dict(r) for r in c.execute("SELECT * FROM groups ORDER BY id")]
        links = [dict(r) for r in c.execute("SELECT * FROM links ORDER BY id DESC")]
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


@app.post("/api/groups")
def create_group():
    d = request.get_json(force=True, silent=True) or {}
    with db() as c:
        gid = get_or_create_group(c, d.get("name"))
        if gid is None:
            return jsonify(error="Give the group a name."), 400
        if d.get("color"):
            c.execute("UPDATE groups SET color=? WHERE id=?", (d["color"], gid))
    return jsonify(id=gid), 201


@app.patch("/api/groups/<int:gid>")
def update_group(gid):
    d = request.get_json(force=True, silent=True) or {}
    with db() as c:
        try:
            if (d.get("name") or "").strip():
                c.execute("UPDATE groups SET name=? WHERE id=?", (d["name"].strip()[:60], gid))
            if d.get("color"):
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
            link_id = add_link(c, url, gid, title)
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
        groups = c.execute("SELECT * FROM groups ORDER BY id").fetchall()
        links = c.execute("SELECT * FROM links ORDER BY id").fetchall()

    def rows(gid, pad):
        return [f'{pad}<DT><A HREF="{e(l["url"])}" ADD_DATE="{l["created_at"]}">{e(l["title"] or l["url"])}</A>'
                for l in links if l["group_id"] == gid]

    for g in groups:
        out += [f'    <DT><H3>{e(g["name"])}</H3>', "    <DL><p>", *rows(g["id"], "        "), "    </DL><p>"]
    out += rows(None, "    ") + ["</DL><p>", ""]
    return Response("\n".join(out), mimetype="text/html",
                    headers={"Content-Disposition": "attachment; filename=linkboard-bookmarks.html"})


init_db()
with db() as _c:  # pick up anything interrupted by a restart
    for _r in _c.execute("SELECT id FROM links WHERE status='pending'").fetchall():
        queue(_r["id"])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
