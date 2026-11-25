"""Check and pack the TileMark browser extension.

    python scripts/build_extension.py          # checks, then writes the two zips below
    python scripts/build_extension.py --check  # only the checks (also run by the tests)

dist/tilemark-extension-<version>.zip          Microsoft Edge Add-ons and the Chrome Web Store
dist/tilemark-extension-<version>-firefox.zip  Firefox Add-ons (addons.mozilla.org)

Both hold the same code. Only manifest.json differs: Firefox gets its add-on ID, the data it
transmits (data_collection_permissions), and background.scripts instead of a service worker.
Checks:
  - manifest.json is valid and every file it names exists;
  - every language has exactly the keys English has, and no text is empty;
  - every text the pages and scripts use (data-i18n="…", t("…"), __MSG_…__) exists;
  - the "{name}" placeholders in each translation match English;
  - the store description fits (at most 132 characters).
"""
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXT = ROOT / "extension"
DIST = ROOT / "dist"
SKIP = {"README.md", "STORE.md", "STORE-CHROME.md", "STORE-FIREFOX.md"}  # notes for people, not part of the extension
SKIP_DIRS = {"store"}  # store pictures (logo, screenshots) are uploaded separately


def _locales():
    out = {}
    for d in sorted((EXT / "_locales").iterdir()):
        with open(d / "messages.json", encoding="utf-8") as f:
            out[d.name] = json.load(f)
    return out


def _used_keys():
    keys = set()
    for path in EXT.rglob("*"):
        if path.suffix == ".html":
            text = path.read_text(encoding="utf-8")
            keys.update(re.findall(r'data-i18n(?:-placeholder|-title|-aria)?="([A-Za-z0-9_]+)"', text))
        elif path.suffix == ".js":
            text = path.read_text(encoding="utf-8")
            keys.update(re.findall(r'\bt\("([A-Za-z0-9_]+)"', text))
            keys.update("err_" + k for k in re.findall(r'new ApiError\("([A-Za-z]+)"', text) if k != "duplicate")
    manifest = (EXT / "manifest.json").read_text(encoding="utf-8")
    keys.update(re.findall(r"__MSG_([A-Za-z0-9_]+)__", manifest))
    return keys


def check():
    """A list of problems; empty when all is well."""
    problems = []
    manifest = json.loads((EXT / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != 3:
        problems.append("manifest_version must be 3")
    named = [manifest["background"]["service_worker"], manifest["action"]["default_popup"], manifest["options_ui"]["page"]]
    named += list(manifest["icons"].values()) + list(manifest["action"]["default_icon"].values())
    problems += [f"manifest names a missing file: {n}" for n in named if not (EXT / n).is_file()]

    locales = _locales()
    if manifest.get("default_locale") not in locales:
        problems.append("default_locale has no folder in _locales")
    en = locales["en"]
    for code, msgs in locales.items():
        missing, extra = set(en) - set(msgs), set(msgs) - set(en)
        problems += [f"{code}: missing {k}" for k in sorted(missing)]
        problems += [f"{code}: not in English: {k}" for k in sorted(extra)]
        for k, v in msgs.items():
            text = v.get("message", "")
            if not text.strip():
                problems.append(f"{code}: {k} is empty")
            if k in en and set(re.findall(r"\{(\w+)\}", text)) != set(re.findall(r"\{(\w+)\}", en[k]["message"])):
                problems.append(f"{code}: {k} has different {{placeholders}} than English")
        if len(msgs.get("extDescription", {}).get("message", "")) > 132:
            problems.append(f"{code}: extDescription is longer than 132 characters")
    problems += [f"text used but not in English: {k}" for k in sorted(_used_keys() - set(en))]
    return problems


# Firefox. The ID is permanent: Firefox Add-ons ties the listing and every update to it.
FIREFOX_ID = "tilemark@sevagjb.github.io"
# What leaves the browser, in Mozilla's words: the API key (authenticationInfo) and the address
# and title of the page the user saves (browsingActivity). It goes only to the user's own
# TileMark, but Mozilla counts anything that leaves the browser. Same as the Chrome listing.
FIREFOX_DATA = ["authenticationInfo", "browsingActivity"]
FIREFOX_MIN = "140.0"  # the first version that knows data_collection_permissions (also the 140 ESR)
FIREFOX_ANDROID_MIN = "142.0"  # the same on Android came two versions later


def firefox_manifest(manifest):
    """manifest.json for Firefox, made from the Edge/Chrome one."""
    m = json.loads(json.dumps(manifest))
    m.pop("minimum_chrome_version", None)
    bg = m.pop("background")
    m["background"] = {"scripts": [bg["service_worker"]], "type": bg.get("type", "classic")}
    m["browser_specific_settings"] = {"gecko": {
        "id": FIREFOX_ID, "strict_min_version": FIREFOX_MIN,
        "data_collection_permissions": {"required": FIREFOX_DATA}},
        "gecko_android": {"strict_min_version": FIREFOX_ANDROID_MIN}}
    return m


def _pack(out, manifest_text):
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", manifest_text)  # manifest.json at the top of the zip
        for path in sorted(EXT.rglob("*")):
            rel = path.relative_to(EXT)
            if (path.is_file() and path.name not in SKIP and path.name != "manifest.json"
                    and not path.name.startswith(".") and rel.parts[0] not in SKIP_DIRS):
                z.write(path, rel.as_posix())
    return out


def build():
    """Writes both zips; returns [Edge/Chrome zip, Firefox zip]."""
    text = (EXT / "manifest.json").read_text(encoding="utf-8")
    manifest = json.loads(text)
    DIST.mkdir(exist_ok=True)
    version = manifest["version"]
    return [_pack(DIST / f"tilemark-extension-{version}.zip", text),
            _pack(DIST / f"tilemark-extension-{version}-firefox.zip",
                  json.dumps(firefox_manifest(manifest), indent=2, ensure_ascii=False) + "\n")]


if __name__ == "__main__":
    found = check()
    for p in found:
        print("✗", p)
    if found:
        sys.exit(1)
    print("✓ extension checks passed")
    if "--check" not in sys.argv:
        for out in build():
            print("✓ wrote", out.relative_to(ROOT))
