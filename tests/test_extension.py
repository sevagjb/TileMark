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
    out = build_extension.build()
    names = zipfile.ZipFile(out).namelist()
    assert "manifest.json" in names and "_locales/ar/messages.json" in names
    assert not any(n.endswith(("STORE.md", "README.md")) or n.startswith("store/") for n in names)
