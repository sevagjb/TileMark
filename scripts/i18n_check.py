#!/usr/bin/env python3
"""Check TileMark's language files, or start a new language.

    python3 scripts/i18n_check.py                  what each language still misses
    python3 scripts/i18n_check.py --new fr Français [--rtl] [--locale fr-FR]
                                                   start pages/lang/fr.json and list it

A new file holds every text with an empty translation; empty texts are shown in English,
so the language can be used (and released) while it is still being translated.
See docs/translating.md.
"""
import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANG = os.path.join(ROOT, "pages", "lang")


def load(name):
    with open(os.path.join(LANG, name), encoding="utf-8") as f:
        return json.load(f)


def save(name, data):
    with open(os.path.join(LANG, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def all_keys(files):
    """Every text any language translates, in the order of the most complete file."""
    order = max(files.values(), key=len) if files else {}
    keys = list(order)
    for tr in files.values():
        keys += [k for k in tr if k not in order and k not in keys]
    return keys


def used_texts():
    """The English text of the pages, the server and the message templates, to spot keys
    that nothing uses any more."""
    out = ""
    for p in ("app.py", "pages/index.html", "pages/login.html", "pages/save.html", "pages/i18n.js"):
        with open(os.path.join(ROOT, p), encoding="utf-8") as f:
            out += f.read()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", nargs=2, metavar=("CODE", "NAME"), help="start a new language, e.g. --new fr Français")
    ap.add_argument("--rtl", action="store_true", help="the new language is written right to left")
    ap.add_argument("--locale", help="date format for the new language, e.g. fr-FR (default: the code)")
    a = ap.parse_args()

    langs = load("languages.json")
    files = {l["code"]: load(l["code"] + ".json") for l in langs if l["code"] != "en"}
    keys = all_keys(files)

    if a.new:
        code, name = a.new
        if not re.fullmatch(r"[a-z]{2,3}(-[A-Za-z0-9]{2,8})?", code):
            sys.exit(f"'{code}' is not a language code like fr, es or pt-BR.")
        if any(l["code"] == code for l in langs):
            sys.exit(f"{code} is already in languages.json.")
        entry = {"code": code, "name": name, "locale": a.locale or code}
        if a.rtl:
            entry["dir"] = "rtl"
        langs.append(entry)
        save("languages.json", langs)
        save(code + ".json", {k: "" for k in keys})
        print(f"Started pages/lang/{code}.json with {len(keys)} texts to translate, and added {name} to languages.json.")
        print("Restart TileMark to see it in Settings → Appearance → Language.")
        return

    used = used_texts()
    for code, tr in files.items():
        empty = [k for k in keys if not tr.get(k)]
        missing = [k for k in keys if k not in tr]
        unused = [k for k in tr if k.split("{")[0][:40].rstrip(".") not in used]
        done = len(keys) - len(empty)
        print(f"{code}: {done} of {len(keys)} translated ({100 * done // max(len(keys), 1)}%)")
        for k in missing:
            print(f"   missing: {k!r}")
        for k in unused:
            print(f"   not used any more? {k!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
