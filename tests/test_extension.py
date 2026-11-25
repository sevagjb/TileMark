"""The browser extension: the same checks scripts/build_extension.py runs before packing."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import build_extension  # noqa: E402


def test_extension_checks_pass():
    assert build_extension.check() == []


def test_extension_zip_has_manifest_at_top(tmp_path, monkeypatch):
    import zipfile
    monkeypatch.setattr(build_extension, "DIST", tmp_path)
    for out in build_extension.build():
        names = zipfile.ZipFile(out).namelist()
        assert names[0] == "manifest.json" and names.count("manifest.json") == 1
        assert "_locales/ar/messages.json" in names and "background.js" in names
        assert not any(n.endswith(("STORE.md", "STORE-CHROME.md", "STORE-FIREFOX.md", "README.md")) or n.startswith("store/") for n in names)


def test_firefox_zip_has_its_own_manifest(tmp_path, monkeypatch):
    import json
    import zipfile
    monkeypatch.setattr(build_extension, "DIST", tmp_path)
    chromium, firefox = build_extension.build()
    assert firefox.name.endswith("-firefox.zip")
    plain = json.loads(zipfile.ZipFile(chromium).read("manifest.json"))
    fx = json.loads(zipfile.ZipFile(firefox).read("manifest.json"))
    # Edge/Chrome: unchanged, a service worker and no Firefox keys
    assert plain["background"] == {"service_worker": "background.js", "type": "module"}
    assert "browser_specific_settings" not in plain
    # Firefox: background scripts, a fixed ID and the data it sends declared
    assert fx["background"] == {"scripts": ["background.js"], "type": "module"}
    gecko = fx["browser_specific_settings"]["gecko"]
    assert gecko["id"] == "tilemark@sevagjb.github.io"
    assert gecko["data_collection_permissions"] == {"required": ["authenticationInfo", "browsingActivity"]}
    assert "minimum_chrome_version" not in fx
    # everything else is the same, so the two stores get the same extension
    for key in ("version", "permissions", "optional_host_permissions", "action", "commands", "options_ui", "icons"):
        assert fx[key] == plain[key], key
