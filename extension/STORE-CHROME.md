# Chrome Web Store: what to fill in

Everything the Chrome Web Store Developer Dashboard asks for, ready to copy. The pictures are in [`store/`](store/); the Edge listing is in [STORE.md](STORE.md). The extension itself is the same for both stores: upload the same zip from `python scripts/build_extension.py` (or from the `ext-v…` release on GitHub).

Tested in Chromium 153: settings and *Save and test*, the toolbar window (title, group, note, Save), and "already saved" for a page that is in TileMark already.

## Before the first upload (once)

1. Open the [Developer Dashboard](https://chrome.google.com/webstore/devconsole) with the Google account that will own the listing. Google advises a separate address just for publishing; the account's email address can't be changed later.
2. Pay the one-time developer registration fee, accept the developer agreement and turn on 2-step verification for the account.
3. **Account** tab: publisher name **sevagjb** (as in Edge), and verify the contact email address. Without a verified address you can't publish.

Then **Items → New item** and upload `dist/tilemark-extension-<version>.zip`. Name, short description, icons and languages come from the zip.

## Package

Same zip as for Edge. Nothing to change in the code: the extension is Manifest V3 for Chromium 116 or later, and opens `chrome://extensions/shortcuts` instead of the Edge page when **Change it** is pressed.

## Store listing

- **Description:** see below.
- **Category:** Productivity → Tools (or Workflow & Planning)
- **Language:** English (the extension itself also comes in Dutch, German, French, Spanish and Arabic)
- **Store icon:** `store/chrome-store-icon-128.png` (128×128, the logo at 96×96 with transparent padding, as Google asks)
- **Screenshots** (1280×800, in this order): `screenshot-1-save.png`, `screenshot-2-saved.png`, `screenshot-3-duplicate.png`, `screenshot-4-settings.png`, `screenshot-5-arabic.png`
- **Small promo tile:** `store/small-tile-440x280.png`
- **Marquee promo tile:** leave empty (optional)
- **Official URL:** leave as *None* (it needs a domain verified in Google Search Console)
- **Homepage URL:** https://sevagjb.github.io/TileMark/browser-extension.html
- **Support URL:** https://github.com/sevagjb/TileMark/issues
- **Mature content:** no

**Description:**

```
Save any web page to your own TileMark in one click.

TileMark is a free, open-source, self-hosted links app: all your saved pages live on one page on your own server (Docker or the Home Assistant app), sorted into groups, each with a picture. This extension adds a "Save to TileMark" button to Chrome.

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

Also works in Brave, Vivaldi and other Chromium browsers.

Guide: https://sevagjb.github.io/TileMark/browser-extension.html
Source code: https://github.com/sevagjb/TileMark
```

Google is strict about keyword lists, so there is no "search terms" field and the description should stay as it is, without a list of keywords at the end.

## Privacy practices

**Single purpose:**

```
Save the current page or a link to the user's own self-hosted TileMark server, with a group and a note.
```

**Permission justifications:**

| Permission | Justification |
| --- | --- |
| activeTab | Reads the address and title of the current tab only when the user clicks the toolbar button or presses the shortcut, so the page can be saved. |
| contextMenus | Adds "Save page to TileMark" and "Save link to TileMark" to the right-click menu. |
| storage | Keeps the user's TileMark address, API key, last used group and language in the browser's local extension storage. |
| Host permission (optional: https://\*/\*, http://\*/\*) | TileMark is self-hosted, so every user has a different server address. The extension never asks for all sites: when the user saves their TileMark address in the settings, it requests access to that one origin only (chrome.permissions.request), and drops it again when the address changes or is removed. |

**Are you using remote code?** No, I am not using remote code. All code is in the package.

**Data usage.** Tick:
- **Authentication information** (the user's own API key for their TileMark)
- **Web history** (the addresses and titles of the pages the user chooses to save)

The developer collects nothing: this data goes only to the TileMark server the user set up. Tick all three statements:
- I do not sell or transfer user data to third parties, outside of the approved use cases
- I do not use or transfer user data for purposes that are unrelated to my item's single purpose
- I do not use or transfer user data to determine creditworthiness or for lending purposes

**Privacy policy URL:** https://sevagjb.github.io/TileMark/extension-privacy.html

## Distribution

- **Payments:** free
- **Visibility:** Public
- **Regions:** all regions

## Test instructions

The reviewer needs a TileMark to try the extension. Use the test TileMark you made for the Edge review (tilemarktest.homeslab.nl), with its non-admin reviewer account, or a new one. Create a **new API key** for this review (name it *Chrome Web Store review*), so you can remove it afterwards without touching the Edge reviewer's key.

**Username / Password:** the reviewer account's sign-in on the test TileMark.

**Additional instructions:**

```
This extension saves pages to the user's own self-hosted TileMark server, so it needs a server address and an API key to work. A test server is ready:

TileMark address: https://tilemarktest.homeslab.nl
API key: <tm_…>

Steps:
1. After installing, the settings page opens. Paste the address and the API key, press "Save and test" and allow access to that address when asked. It shows "Connected. Groups found: <n>."
2. Open any web page and click the TileMark toolbar button. Pick a group, type a note, press Save: "Saved to <group>".
3. Click the button again on the same page and press Save: it says the page is already saved and in which group.
4. Right-click a link → "Save link to TileMark": the toolbar icon shows ✓.
5. To see the saved links, open the address above and sign in with the username and password given in this form.

Host permissions are optional and requested at runtime for the one address the user enters; the extension never asks for all sites. No remote code; the source is at https://github.com/sevagjb/TileMark/tree/main/extension.
```

## After submitting

Review usually takes a few days, sometimes longer for a first item. Keep the test server running until the extension is published. Then:

1. Remove the *Chrome Web Store review* API key.
2. Add the store link to the guide (`docs/browser-extension.md`), the README and the roadmap, as was done for Edge in PR #42. The listing address only exists after publishing.
3. Updates: upload the new zip in the dashboard (**Package → Upload new package**) and submit for review. Edge and Chrome are updated separately, with the same zip.
