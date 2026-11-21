# Microsoft Edge Add-ons: what to fill in

Everything Partner Center asks for, ready to copy. The pictures are in [`store/`](store/). Upload the zip from `python scripts/build_extension.py` (or from the `ext-v…` release on GitHub).

## Package

Upload `dist/tilemark-extension-<version>.zip`. Name, short description and icons come from the zip.

## Availability

- **Visibility:** Public
- **Markets:** all markets

## Properties

- **Category:** Productivity
- **Website:** https://sevagjb.github.io/TileMark/browser-extension.html
- **Support contact:** https://github.com/sevagjb/TileMark/issues
- **Mature content:** no

## Privacy

- **Privacy policy URL:** https://sevagjb.github.io/TileMark/extension-privacy.html
- **Single purpose:** Save the current page or a link to the user's own self-hosted TileMark server, with a group and a note.
- **Remote code:** No. All code is in the package.

**Permission justifications**

| Permission | Justification |
| --- | --- |
| activeTab | Reads the address and title of the current tab only when the user clicks the toolbar button or presses the shortcut, so the page can be saved. |
| contextMenus | Adds "Save page to TileMark" and "Save link to TileMark" to the right-click menu. |
| storage | Keeps the user's TileMark address, API key, last used group and language in the browser's local extension storage. |
| Host permissions (optional: https://\*/\*, http://\*/\*) | TileMark is self-hosted, so every user has a different server address. The extension never asks for all sites: when the user saves their TileMark address in the settings, it requests access to that one origin only (chrome.permissions.request), and drops it again when the address changes or is removed. |

**Data usage.** The developer collects nothing. The extension sends the address and title of a page the user chooses to save, plus the user's API key, only to the TileMark server the user configured. The careful choice is to declare:
- **Web history** (the addresses of pages the user chooses to save), and
- **Authentication information** (the user's own API key for their TileMark),

and to certify that the data is not sold, not used for anything unrelated to the single purpose, and not used for creditworthiness.

## Store listing (English)

**Description** (250 to 10,000 characters):

```
Save any web page to your own TileMark in one click.

TileMark is a free, open-source, self-hosted links app: all your saved pages live on one page on your own server (Docker or the Home Assistant app), sorted into groups, each with a picture. This extension adds a "Save to TileMark" button to Edge.

• Toolbar button: the page's title, a group (the one you used last is already chosen, or make a new one), an optional note, Save.
• Right-click a page or a link: "Save page to TileMark" or "Save link to TileMark" saves straight away.
• Keyboard shortcut: Alt+Shift+S opens the Save window.
• Already saved? It tells you in which group, instead of saving the page twice.
• In English, Nederlands, Deutsch, Français, Español and العربية (right to left).

Private by design:
• It talks only to your own TileMark, using your API key. There is no TileMark cloud and no account with the developer.
• It asks for access to your TileMark's address only, never to all websites.
• No analytics, no tracking. The address and key stay in this browser and are never synced.

You need a running TileMark (version 2.9 or later) and an API key from Your account → Save from anywhere. Setup takes a minute: paste your TileMark address and the key, press "Save and test".

Guide: https://sevagjb.github.io/TileMark/browser-extension.html
Source code: https://github.com/sevagjb/TileMark
```

- **Extension logo:** `store/store-logo-300.png` (300×300)
- **Small promotional tile:** `store/small-tile-440x280.png` (optional)
- **Screenshots** (1280×800, in this order): `screenshot-1-save.png`, `screenshot-2-saved.png`, `screenshot-3-duplicate.png`, `screenshot-4-settings.png`, `screenshot-5-arabic.png`
- **Search terms** (up to 7, 30 characters each, 21 words in total): `TileMark`, `self-hosted bookmarks`, `read later`, `link saver`, `Home Assistant`, `homelab`, `bookmark manager`

Other languages can be added later with **Duplicate** for the pictures; the description then needs translating.

## Notes for certification

The reviewer needs a TileMark to try the extension. Before submitting, start a test TileMark that the reviewer can reach (a separate container, not your own library), create an account `reviewer` with a few groups, create its API key, and fill in the two lines below:

```
This extension saves pages to the user's own self-hosted TileMark server, so it needs a server address and an API key to work. A test server is ready:

TileMark address: <https://test-address>
API key: <tm_…>

Steps:
1. After installing, the settings page opens. Paste the address and the API key, press "Save and test" and allow access to that address when asked. It shows "Connected. Groups found: 3."
2. Open any web page and click the TileMark toolbar button. Pick a group, type a note, press Save: "Saved to <group>".
3. Click the button again on the same page: it says the page is already saved and in which group.
4. Right-click a link → "Save link to TileMark": the toolbar icon shows ✓.
5. To see the saved links, open the address above and sign in as: reviewer / <password>

Host permissions are optional and requested at runtime for the one address the user enters; the extension never asks for all sites. No remote code; the source is at https://github.com/sevagjb/TileMark/tree/main/extension.
```

Microsoft's review can take up to seven business days. Keep the test server running until the extension is published, and remove the reviewer account afterwards.
