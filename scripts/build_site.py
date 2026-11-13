"""Build the TileMark website from the guide in docs/.

    pip install markdown
    python scripts/build_site.py          # writes _site/

The Markdown pages in docs/ are the source; they also read well on GitHub itself.
This script wraps them in the site's layout, adds the landing page, and fixes links
(.md becomes .html; links outside docs/ go to the repository on GitHub).
"""
import html
import re
import shutil
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
DOCS, SITE, OUT = ROOT / "docs", ROOT / "scripts" / "site", ROOT / "_site"
REPO = "https://github.com/sevagjb/TileMark"

# (file in docs/, title in the menu). The order is the order of the menu.
PAGES = [
    ("getting-started.md", "Getting started"),
    ("home-assistant-add-on.md", "Home Assistant add-on"),
    ("links-and-groups.md", "Links and groups"),
    ("import-export.md", "Import and export"),
    ("save-from-anywhere.md", "Save from anywhere"),
    ("broken-links.md", "Broken links"),
    ("accounts-and-security.md", "Accounts and security"),
    ("backups.md", "Backups"),
    ("home-assistant-sensors.md", "Home Assistant sensors"),
    ("settings.md", "Settings"),
    ("faq.md", "Questions and troubleshooting"),
]
EXTRA = [("CHANGELOG.md", "changelog.md", "Changelog"), ("ROADMAP.md", "roadmap.md", "Roadmap")]  # from the repository root


def slug(text):
    """Heading ids the way GitHub makes them, so the same #links work on both."""
    text = re.sub(r"<[^>]+>", "", text).strip().lower()
    text = re.sub(r"[^\w\- ]", "", text)
    return text.replace(" ", "-")


def fix_links(body):
    def href(m):
        url = m.group(1)
        if re.match(r"^(https?:|mailto:|#)", url):
            return m.group(0)
        path, _, frag = url.partition("#")
        frag = "#" + frag if frag else ""
        if path in ("../CHANGELOG.md", "CHANGELOG.md"):
            return f'href="changelog.html{frag}"'
        if path in ("../ROADMAP.md", "ROADMAP.md"):
            return f'href="roadmap.html{frag}"'
        if path.startswith("../"):
            return f'href="{REPO}/blob/main/{path[3:]}{frag}"'
        if path == "README.md":
            return f'href="guide.html{frag}"'
        if path.endswith(".md"):
            return f'href="{path[:-3]}.html{frag}"'
        return m.group(0)
    return re.sub(r'href="([^"]*)"', href, body)


def render(text):
    md = markdown.Markdown(extensions=["tables", "fenced_code", "toc", "sane_lists", "attr_list"],
                           extension_configs={"toc": {"slugify": lambda t, sep: slug(t), "toc_depth": "2-3"}})
    body = md.convert(text)
    body = fix_links(body)
    body = re.sub(r"<table>", '<div class="tw"><table>', body).replace("</table>", "</table></div>")
    body = re.sub(r'<img ', '<img loading="lazy" ', body)
    return body, md.toc_tokens


def page(template, title, body, current, toc_tokens=()):
    nav = "".join(
        f'<a href="{f[:-3]}.html"{" class=on" if f == current else ""}>{html.escape(t)}</a>' for f, t in PAGES)
    nav += '<hr>' + "".join(
        f'<a href="{o[:-3]}.html"{" class=on" if o == current else ""}>{t}</a>' for _, o, t in EXTRA)
    toc = ""
    heads = list(toc_tokens)  # the page's sections (h2)
    if len(heads) >= 3:
        toc = '<nav class="toc"><b>On this page</b>' + "".join(
            f'<a href="#{h["id"]}">{h["name"]}</a>' for h in heads) + "</nav>"
    src = f"docs/{current}" if current in dict(PAGES) else next((s for s, o, _ in EXTRA if o == current), "")
    edit = f'<p class="edit"><a href="{REPO}/edit/main/{src}">Improve this page on GitHub</a></p>' if src else ""
    return (template.replace("{{title}}", html.escape(title)).replace("{{nav}}", nav)
            .replace("{{body}}", f'<article>{body}{edit}</article>{toc}'))


def main():
    template = (SITE / "page.html").read_text(encoding="utf-8")
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copytree(DOCS / "images", OUT / "images")
    for f in ("style.css",):
        shutil.copy(SITE / f, OUT / f)
    for f in ("logo.svg", "logo.png", "logo-128.png"):
        shutil.copy(DOCS / f, OUT / f)
    (OUT / ".nojekyll").write_text("")

    for name, title in PAGES:
        body, toc = render((DOCS / name).read_text(encoding="utf-8"))
        (OUT / (name[:-3] + ".html")).write_text(page(template, title, body, name, toc), encoding="utf-8")
    for src, name, title in EXTRA:
        body, toc = render((ROOT / src).read_text(encoding="utf-8"))
        (OUT / (name[:-3] + ".html")).write_text(page(template, title, body, name), encoding="utf-8")
    body, _ = render((DOCS / "README.md").read_text(encoding="utf-8"))
    (OUT / "guide.html").write_text(page(template, "Guide", body, "README.md"), encoding="utf-8")

    landing = (SITE / "index.html").read_text(encoding="utf-8")
    (OUT / "index.html").write_text(landing, encoding="utf-8")

    # every local link must point at a page or file that exists
    bad = []
    for f in OUT.glob("*.html"):
        for m in re.finditer(r'(?:href|src)="([^"#:]+)(#[^"]*)?"', f.read_text(encoding="utf-8")):
            if not (OUT / m.group(1)).exists():
                bad.append(f"{f.name}: {m.group(1)}")
    # and every #anchor must exist on the page it points to
    ids = {f.name: set(re.findall(r'id="([^"]+)"', f.read_text(encoding="utf-8"))) for f in OUT.glob("*.html")}
    for f in OUT.glob("*.html"):
        for m in re.finditer(r'href="([^"#:]*)#([^"]+)"', f.read_text(encoding="utf-8")):
            target = m.group(1) or f.name
            if target in ids and m.group(2) not in ids[target]:
                bad.append(f"{f.name}: {target}#{m.group(2)}")
    if bad:
        sys.exit("Broken links:\n" + "\n".join(bad))
    print(f"Built {len(list(OUT.glob('*.html')))} pages in {OUT}")


if __name__ == "__main__":
    main()
