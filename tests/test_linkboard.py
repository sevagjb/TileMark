"""Tests for LinkBoard 1.1: upgrade from 1.0, first start, several users, safe fetching.

Run: pip install -r requirements.txt pytest && pytest -q
"""
import importlib
import io
import os
import sqlite3
import sys
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["LINKBOARD_NO_WORKERS"] = "1"
for _var in ("NO_PROXY", "no_proxy"):  # the local test servers are reached directly
    os.environ[_var] = ",".join(filter(None, [os.environ.get(_var, ""), "127.0.0.1", "localhost"]))

# The 1.0 schema, exactly as LinkBoard 1.0 left it after all its column upgrades.
V1_SCHEMA = """
CREATE TABLE groups (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    color TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0);
CREATE TABLE links (id INTEGER PRIMARY KEY AUTOINCREMENT, url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL DEFAULT '', description TEXT NOT NULL DEFAULT '', thumb TEXT NOT NULL DEFAULT '',
    thumb_kind TEXT NOT NULL DEFAULT '', group_id INTEGER REFERENCES groups(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending', custom_title INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL,
    position INTEGER NOT NULL DEFAULT 0, pinned INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
    opened_at INTEGER NOT NULL DEFAULT 0, custom_thumb INTEGER NOT NULL DEFAULT 0,
    broken INTEGER NOT NULL DEFAULT 0, checked_at INTEGER NOT NULL DEFAULT 0);
CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
INSERT INTO groups (id, name, color, position) VALUES (1, 'HomeLab', '#123456', 1), (2, 'News', '#654321', 2);
INSERT INTO links (id, url, title, group_id, status, created_at, position, thumb, note, pinned) VALUES
    (1, 'https://proxmox.com', 'Proxmox', 1, 'ok', 1, -1, '1-1.webp', 'hypervisor', 1),
    (2, 'http://192.168.1.10', 'NAS', NULL, 'ok', 2, -2, '', '', 0),
    (3, 'https://nos.nl', 'NOS', 2, 'ok', 3, -3, '', '', 0);
"""


def load_app(data_dir):
    os.environ["DATA_DIR"] = str(data_dir)
    sys.modules.pop("app", None)
    mod = importlib.import_module("app")
    mod.queue = lambda link_id: None  # no fetching from the internet during tests
    return mod


def make_v1(data_dir, login=True):
    os.makedirs(os.path.join(data_dir, "thumbs"), exist_ok=True)
    con = sqlite3.connect(os.path.join(data_dir, "linkboard.db"))
    con.executescript(V1_SCHEMA)
    if login:
        from werkzeug.security import generate_password_hash
        import hashlib
        con.executemany("INSERT INTO settings VALUES (?, ?)", [
            ("auth_user", "Sevag"), ("auth_hash", generate_password_hash("secret123")), ("auth_ver", "abc"),
            ("api_key_hash", hashlib.sha256(b"lb_oldkey").hexdigest()), ("secret_key", "s" * 64)])
    con.commit()
    con.close()
    with open(os.path.join(data_dir, "thumbs", "1-1.webp"), "wb") as f:
        f.write(b"old picture")


@pytest.fixture
def fresh(tmp_path):
    return load_app(tmp_path)


def setup_admin(A, name="admin", pw="adminpass1"):
    c = A.app.test_client()
    assert c.post("/api/setup", json={"username": name, "password": pw}).status_code == 201
    return c


def add_user(admin, name, pw="userpass11"):
    assert admin.post("/api/users", json={"username": name, "password": pw}).status_code == 201


def sign_in(A, name, pw):
    c = A.app.test_client()
    assert c.post("/api/login", json={"username": name, "password": pw}).status_code == 200
    return c


# ------------------------------------------------------------------ upgrade
def test_upgrade_from_v1_with_login(tmp_path):
    make_v1(tmp_path)
    A = load_app(tmp_path)
    c = A.app.test_client()
    assert c.get("/api/state").status_code == 401  # old sessions end; sign in again
    c = sign_in(A, "sevag", "secret123")  # username stays case-insensitive
    s = c.get("/api/state").get_json()
    assert s["me"] == {"username": "Sevag", "is_admin": True}
    assert {l["url"] for l in s["links"]} == {"https://proxmox.com", "http://192.168.1.10", "https://nos.nl"}
    assert {g["name"] for g in s["groups"]} == {"HomeLab", "News"}
    p = next(l for l in s["links"] if l["id"] == 1)
    assert (p["note"], p["pinned"], p["group_id"]) == ("hypervisor", 1, 1)
    assert c.get("/thumbs/1-1.webp").status_code == 200
    # the old API key keeps working, now as this user's key
    r = A.app.test_client().post("/api/links", json={"url": "https://ha.io"}, headers={"Authorization": "Bearer lb_oldkey"})
    assert r.status_code == 201
    con = sqlite3.connect(os.path.join(tmp_path, "linkboard.db"))
    keys = {r[0] for r in con.execute("SELECT key FROM settings")}
    assert not keys & {"auth_user", "auth_hash", "auth_ver", "api_key_hash"}
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_upgrade_is_done_once(tmp_path):
    make_v1(tmp_path)
    load_app(tmp_path)
    A = load_app(tmp_path)  # second start: nothing changes
    c = sign_in(A, "Sevag", "secret123")
    assert len(c.get("/api/state").get_json()["links"]) == 3


def test_upgrade_open_v1_claimed_by_first_account(tmp_path):
    make_v1(tmp_path, login=False)
    A = load_app(tmp_path)
    c = A.app.test_client()
    r = c.get("/api/state")
    assert r.status_code == 401 and r.get_json()["setup"] is True
    assert c.get("/api/auth").get_json()["setup"] is True
    c = setup_admin(A, "Sevag")
    assert len(c.get("/api/state").get_json()["links"]) == 3


# -------------------------------------------------------------- first start
def test_new_install_is_never_open(fresh):
    c = fresh.app.test_client()
    assert c.get("/api/state").status_code == 401
    assert c.post("/api/links", json={"url": "https://example.com"}).status_code == 401
    assert c.get("/").status_code == 302 and c.get("/").headers["Location"].endswith("/login")
    assert c.get("/login").status_code == 200


def test_setup_only_once(fresh):
    setup_admin(fresh)
    other = fresh.app.test_client()
    assert other.post("/api/setup", json={"username": "evil", "password": "evilpass11"}).status_code == 409
    assert other.get("/api/auth").get_json()["setup"] is False


def test_setup_validates(fresh):
    c = fresh.app.test_client()
    assert c.post("/api/setup", json={"username": "a", "password": "short"}).status_code == 400
    assert c.post("/api/setup", json={"username": "", "password": "longenough"}).status_code == 400


# ------------------------------------------------------------- isolation
@pytest.fixture
def two(fresh):
    """Admin with one link + group; user bob with one link + group."""
    A = fresh
    admin = setup_admin(A)
    add_user(admin, "bob")
    bob = sign_in(A, "bob", "userpass11")
    ga = admin.post("/api/groups", json={"name": "Shared name"}).get_json()["id"]
    gb = bob.post("/api/groups", json={"name": "Shared name"}).get_json()["id"]  # same name is fine per user
    la = admin.post("/api/links", json={"url": "https://admin.example", "group_id": ga}).get_json()["id"]
    lb = bob.post("/api/links", json={"url": "https://admin.example", "group_id": gb}).get_json()["id"]  # same URL too
    with A.db() as c:
        c.execute("UPDATE links SET thumb=? WHERE id=?", (f"{la}-a.webp", la))
        c.execute("UPDATE links SET thumb=? WHERE id=?", (f"{lb}-b.webp", lb))
    for name in (f"{la}-a.webp", f"{lb}-b.webp"):
        with open(os.path.join(A.THUMB_DIR, name), "wb") as f:
            f.write(b"pic")
    return A, admin, bob, ga, gb, la, lb


def test_users_see_only_their_own(two):
    A, admin, bob, ga, gb, la, lb = two
    sa, sb = admin.get("/api/state").get_json(), bob.get("/api/state").get_json()
    assert [l["id"] for l in sa["links"]] == [la] and [l["id"] for l in sb["links"]] == [lb]
    assert [g["id"] for g in sa["groups"]] == [ga] and [g["id"] for g in sb["groups"]] == [gb]
    assert [g["id"] for g in bob.get("/api/groups").get_json()["groups"]] == [gb]
    assert "admin.example" in admin.get("/api/export").get_data(as_text=True)
    assert bob.get(f"/thumbs/{la}-a.webp").status_code == 404
    assert bob.get(f"/thumbs/{lb}-b.webp").status_code == 200
    assert "private" in bob.get(f"/thumbs/{lb}-b.webp").headers["Cache-Control"]
    assert "admin" not in sb and sb["me"]["is_admin"] is False


def test_users_cannot_touch_each_other(two):
    A, admin, bob, ga, gb, la, lb = two
    assert bob.patch(f"/api/links/{la}", json={"title": "hacked"}).status_code == 404
    assert bob.patch(f"/api/links/{lb}", json={"group_id": ga}).status_code == 404  # someone else's group
    assert bob.post(f"/api/links/{la}/refresh").status_code == 404
    assert bob.delete(f"/api/links/{la}/thumb").status_code == 404
    assert bob.post(f"/api/links/{la}/thumb", data={"file": (io.BytesIO(b"x"), "a.png")}).status_code == 404
    bob.delete(f"/api/links/{la}")
    bob.post(f"/api/links/{la}/opened")
    assert bob.post("/api/links/bulk", json={"ids": [la], "delete": True}).status_code == 400
    assert bob.post("/api/links/bulk", json={"ids": [lb], "group_id": ga}).status_code == 404
    bob.post("/api/links/order", json={"ids": [la, lb]})
    assert bob.patch(f"/api/groups/{ga}", json={"name": "hacked"}).status_code == 404
    assert bob.delete(f"/api/groups/{ga}?links=1").status_code == 404
    bob.post("/api/groups/order", json={"ids": [ga]})
    r = bob.post("/api/import", data={"text": "https://new.example", "group_id": str(ga)})
    assert r.get_json()["added"] == 1
    assert bob.post("/api/links", json={"url": "https://x.example", "group_id": ga}).status_code == 201
    s = admin.get("/api/state").get_json()
    assert len(s["links"]) == 1 and s["links"][0]["title"] != "hacked" and s["links"][0]["opened_at"] == 0
    assert s["groups"][0]["name"] == "Shared name"
    with A.db() as c:  # bob's new links did not land in admin's group
        assert c.execute("SELECT COUNT(*) FROM links WHERE group_id=?", (ga,)).fetchone()[0] == 1
    assert os.path.exists(os.path.join(A.THUMB_DIR, f"{la}-a.webp"))


def test_api_key_is_per_user(two):
    A, admin, bob, *_ = two
    key = bob.post("/api/apikey").get_json()["key"]
    anon = A.app.test_client()
    h = {"Authorization": "Bearer " + key}
    assert anon.post("/api/links", json={"url": "https://via-key.example"}, headers=h).status_code == 201
    assert anon.get("/api/state", headers=h).status_code == 401  # a key can only add and read group names
    assert len(bob.get("/api/state").get_json()["links"]) == 2
    assert len(admin.get("/api/state").get_json()["links"]) == 1
    assert anon.post("/api/links", json={"url": "https://y.example"}, headers={"Authorization": "Bearer nope"}).status_code == 401


def test_admin_only_endpoints(two):
    A, admin, bob, *_ = two
    assert bob.get("/api/users").status_code == 403
    assert bob.post("/api/users", json={"username": "x", "password": "longenough"}).status_code == 403
    assert bob.post("/api/settings", json={"fetch_private": True}).status_code == 403
    assert admin.get("/api/users").status_code == 200


def test_backup_restore_per_user(two):
    A, admin, bob, ga, gb, la, lb = two
    data = bob.post("/api/backup", json={"password": "bk-pass"}).get_data()
    with pytest.raises(A.RestoreError):
        A.restore_backup(1, data, "wrong")
    plain = bob.post("/api/backup", json={}).get_data()
    z = zipfile.ZipFile(io.BytesIO(plain))
    assert sorted(z.namelist()) == ["linkboard.db", f"thumbs/{lb}-b.webp"]  # nothing of admin's
    bob.post("/api/links", json={"url": "https://after-backup.example"})
    r = bob.post("/api/restore", data={"file": (io.BytesIO(data), "b.lbk"), "password": "bk-pass"})
    assert r.status_code == 200 and r.get_json()["links"] == 1
    sb = bob.get("/api/state").get_json()
    assert [l["url"] for l in sb["links"]] == ["https://admin.example"]
    assert sb["links"][0]["group_id"] == sb["groups"][0]["id"]
    assert bob.get("/thumbs/" + sb["links"][0]["thumb"]).status_code == 200
    sa = admin.get("/api/state").get_json()  # admin untouched
    assert [l["id"] for l in sa["links"]] == [la] and admin.get(f"/thumbs/{la}-a.webp").status_code == 200


def test_restore_v1_backup_into_user(two, tmp_path):
    A, admin, bob, *_ = two
    v1 = tmp_path / "v1"
    make_v1(v1)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.write(v1 / "linkboard.db", "linkboard.db")
        z.write(v1 / "thumbs" / "1-1.webp", "thumbs/1-1.webp")
    r = bob.post("/api/restore", data={"file": (io.BytesIO(buf.getvalue()), "old.zip")})
    assert r.get_json() == {"ok": True, "links": 3, "groups": 2}
    sb = bob.get("/api/state").get_json()
    prox = next(l for l in sb["links"] if l["url"] == "https://proxmox.com")
    assert prox["thumb"] and bob.get("/thumbs/" + prox["thumb"]).status_code == 200
    assert {g["name"] for g in sb["groups"]} == {"HomeLab", "News"}
    assert len(admin.get("/api/state").get_json()["links"]) == 1


def test_delete_user_removes_everything(two):
    A, admin, bob, ga, gb, la, lb = two
    bob_id = next(u["id"] for u in admin.get("/api/users").get_json()["users"] if u["username"] == "bob")
    assert admin.delete(f"/api/users/{bob_id}").status_code == 200
    assert bob.get("/api/state").status_code == 401
    assert not os.path.exists(os.path.join(A.THUMB_DIR, f"{lb}-b.webp"))
    with A.db() as c:
        assert c.execute("SELECT COUNT(*) FROM links WHERE user_id=?", (bob_id,)).fetchone()[0] == 0
        assert c.execute("SELECT COUNT(*) FROM groups WHERE user_id=?", (bob_id,)).fetchone()[0] == 0
    me = next(u["id"] for u in admin.get("/api/users").get_json()["users"] if u["me"])
    assert admin.delete(f"/api/users/{me}").status_code == 400


def test_last_admin_and_password_reset(two):
    A, admin, bob, *_ = two
    users = admin.get("/api/users").get_json()["users"]
    me = next(u["id"] for u in users if u["me"])
    bob_id = next(u["id"] for u in users if u["username"] == "bob")
    assert admin.patch(f"/api/users/{me}", json={"is_admin": False}).status_code == 400
    assert admin.patch(f"/api/users/{bob_id}", json={"username": "admin"}).status_code == 409
    assert admin.patch(f"/api/users/{bob_id}", json={"username": "robert", "password": "short"}).status_code == 400
    assert admin.get("/api/users").get_json()["users"][1]["username"] == "bob"  # nothing half-changed
    assert admin.patch(f"/api/users/{bob_id}", json={"password": "newpass123"}).status_code == 200
    assert bob.get("/api/state").status_code == 401  # signed out everywhere
    sign_in(A, "bob", "newpass123")


def test_account_change_and_cli_reset(two):
    A, admin, bob, *_ = two
    assert bob.post("/api/account", json={"username": "bob", "password": "x" * 8, "current_password": "bad"}).status_code == 403
    assert bob.post("/api/account", json={"username": "admin", "current_password": "userpass11"}).status_code == 409
    assert bob.post("/api/account", json={"username": "bobby", "password": "bobbypass1",
                                          "current_password": "userpass11"}).status_code == 200
    assert bob.get("/api/state").get_json()["me"]["username"] == "bobby"  # this device stays signed in
    who, pw = A.reset_login()
    assert who == "admin" and admin.get("/api/state").status_code == 401
    sign_in(A, "admin", pw)


def test_prefs_are_per_user_and_validated(two):
    A, admin, bob, *_ = two
    bob.put("/api/prefs", json={"layout": "sections", "theme": "dark", "sorts": {"3": "name", "4": "evil"}})
    admin.put("/api/prefs", json={"layout": "bogus"})
    assert bob.get("/api/state").get_json()["prefs"] == {"layout": "sections", "theme": "dark", "sorts": {"3": "name"}}
    assert admin.get("/api/state").get_json()["prefs"] == {}


# ------------------------------------------------------------ safe fetching
@pytest.mark.parametrize("addr,private,ok", [
    ("8.8.8.8", False, True), ("2606:4700:4700::1111", False, True),
    ("127.0.0.1", True, False), ("::1", True, False), ("169.254.169.254", True, False),
    ("0.0.0.0", True, False), ("0.1.2.3", True, False), ("224.0.0.1", True, False), ("fe80::1", True, False),
    ("::ffff:127.0.0.1", True, False), ("::ffff:192.168.1.10", False, False),
    ("192.168.1.10", False, False), ("10.0.0.5", False, False), ("172.16.0.1", False, False), ("fd00::1", False, False),
    ("192.168.1.10", True, True), ("10.0.0.5", True, True), ("100.64.0.1", True, True), ("garbage", True, False),
])
def test_addr_rules(fresh, addr, private, ok):
    assert fresh._addr_allowed(addr, private) is ok


class _Handler(BaseHTTPRequestHandler):
    target = ""

    def do_GET(self):
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", _Handler.target)
            self.end_headers()
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<title>secret local page</title>")

    def log_message(self, *a):
        pass


@pytest.fixture
def local_server():
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}"
    srv.shutdown()


@pytest.mark.parametrize("url", ["http://127.0.0.1:{port}/", "http://localhost:{port}/", "http://[::1]:{port}/",
                                 "http://2130706433:{port}/", "http://0x7f.1:{port}/", "http://169.254.169.254/latest",
                                 "http://0.0.0.0:{port}/", "ftp://example.com/", "file:///etc/passwd"])
def test_local_addresses_are_refused(fresh, local_server, url):
    port = local_server.rsplit(":", 1)[1]
    with pytest.raises((fresh.Blocked, requests.ConnectionError)):
        fresh.safe_get(url.format(port=port))
    fresh.set_setting("fetch_private", "on")  # loopback stays refused even then
    with pytest.raises((fresh.Blocked, requests.ConnectionError)):
        fresh.safe_get(url.format(port=port))


def test_redirect_to_local_is_refused(fresh, local_server, monkeypatch):
    """The first address is allowed (pretend it is public); its redirect to the
    metadata address must be checked again and refused."""
    real = fresh._addr_allowed
    monkeypatch.setattr(fresh, "_addr_allowed", lambda a, p: a == "127.0.0.1" or real(a, p))
    _Handler.target = "http://169.254.169.254/latest/meta-data/"
    with pytest.raises(fresh.Blocked):
        fresh.safe_get(local_server + "/redirect")
    _Handler.target = "/page"  # a redirect to an allowed address is followed
    r = fresh.safe_get(local_server + "/redirect")
    assert r.status_code == 200 and r.url.endswith("/page")
    r.close()


def test_rebinding_caught_at_connect(fresh, local_server, monkeypatch):
    """Even if the name check is fooled (DNS answers differently the second time),
    the address actually connected to is checked."""
    monkeypatch.setattr(fresh, "_host_allowed", lambda h, p, a: True)
    with pytest.raises(fresh.Blocked):
        fresh.safe_get(local_server + "/")


def test_lan_link_saved_but_not_fetched(fresh, local_server, monkeypatch):
    """A link to a local address can be saved; its preview is skipped without errors,
    and the link check does not call it broken."""
    c = setup_admin(fresh)
    lid = c.post("/api/links", json={"url": local_server + "/"}).get_json()["id"]
    fresh.fetch_meta(lid)
    with fresh.db() as con:
        row = con.execute("SELECT title, thumb FROM links WHERE id=?", (lid,)).fetchone()
    assert "secret" not in row["title"] and row["thumb"] == ""
    assert fresh._probe(local_server + "/") == "unknown"
