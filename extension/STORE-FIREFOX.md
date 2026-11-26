# Firefox Add-ons: what to fill in

Everything addons.mozilla.org (AMO) asks for, ready to copy. The pictures are in [`store/`](store/); Edge is in [STORE.md](STORE.md), Chrome in [STORE-CHROME.md](STORE-CHROME.md).

Firefox gets its **own zip**: `dist/tilemark-extension-<version>-firefox.zip` from `python scripts/build_extension.py` (or from the `ext-v…` release on GitHub). It holds the same code as the Edge/Chrome zip; only `manifest.json` differs:

- **Add-on ID** `tilemark@sevagjb.github.io`. Firefox ties the listing and every update to it, so it never changes.
- **Data it sends**, declared for Firefox's install prompt (`data_collection_permissions`): *authentication information* (the API key) and *browsing activity* (the address and title of a page you save). It goes only to your own TileMark, but Mozilla counts anything that leaves the browser, so `none` would be wrong. This matches the Chrome listing.
- **Firefox 140 or later** (Android 142 or later); `background.scripts` instead of Chrome's service worker.
- **Ctrl+Shift+L** as the keyboard shortcut instead of Alt+Shift+S, which opens Firefox's History menu (Alt+S). The settings page shows whichever shortcut the browser really uses.

Mozilla's linter (`addons-linter`, the check AMO runs on upload) reports 0 errors and 0 warnings for this zip.

## Try it in your own Firefox first

1. Open `about:debugging#/runtime/this-firefox` and press **Load Temporary Add-on…**.
2. Choose the Firefox zip (no need to unzip). The settings page opens.
3. Enter your TileMark address and an API key, press **Save and test**, and allow access when Firefox asks.
4. Try the toolbar button, the right-click menu, **Ctrl+Shift+L**, and **Change it** in the settings (it should open Firefox's shortcut settings in `about:addons`).

A temporary add-on stays until Firefox restarts. Installing it for good only works once AMO has signed it.

## Before the first upload (once)

1. Sign in at the [Add-on Developer Hub](https://addons.mozilla.org/developers/) with a Mozilla account, the same kind you'd use for Firefox Sync.
2. Accept the Firefox Add-on Distribution Agreement and set a display name: **sevagjb**, as in Edge and Chrome.
3. If AMO asks, turn on two-step authentication for the Mozilla account. It's needed before you can submit.

## Submit

**Submit a New Add-on** → **On this site** (the public listing).

- **Upload:** the `-firefox.zip`.
- **Compatible with:** tick **Firefox** only for now. The extension doesn't break on Android (it skips the right-click menu there), but the toolbar window hasn't been tried on a phone yet.
- **Do you need to submit source code?** **No.** Nothing is minified, bundled or generated; the files in the zip are the source.

### Describe the add-on

- **Name:** comes from the zip (TileMark).
- **Add-on URL:** `tilemark`
- **Summary** (at most 250 characters):

```
Save any web page to your own self-hosted TileMark in one click: toolbar button with group and note, right-click menu and a keyboard shortcut. Talks only to your own server.
```

- **Description:**

```
Save any web page to your own TileMark in one click.

TileMark is a free, open-source, self-hosted links app: all your saved pages live on one page on your own server (Docker or the Home Assistant app), sorted into groups, each with a picture. This extension adds a "Save to TileMark" button to Firefox.

• Toolbar button: the page's title, a group (the one you used last is already chosen, or make a new one), an optional note, Save.
• Right-click a page or a link: "Save page to TileMark" or "Save link to TileMark" saves straight away.
• Keyboard shortcut: Ctrl+Shift+L opens the Save window.
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

- **Experimental / requires payment:** no, no.
- **Category:** **Bookmarks**.
- **Support email:** the contact address you want to show (the same as for Chrome is fine).
- **Support website:** `https://github.com/sevagjb/TileMark/issues`
- **License:** **MIT License** (the same as the repository).
- **Privacy policy:** tick **This add-on has a privacy policy** and paste:

```
The TileMark extension sends pages only to your own TileMark server. It has no server of its own, and the developer receives nothing.

What it sends, and where: when you press Save, or choose "Save page/link to TileMark" in the right-click menu, it sends to the TileMark address you entered: the address of the page or link, the page's title, the group and note you chose, and your API key. To fill the group list it asks that TileMark for your group names. Nothing is sent at any other moment; it does not watch your browsing.

What it stores: in this browser only (local extension storage, never synced): your TileMark address, API key, last used group and your language and menu choices. "Remove the address and key from this browser" in the settings, or uninstalling, deletes all of it.

What it does not do: no analytics, tracking, advertising or crash reports. Nothing goes to the developer or any third party. No selling or sharing of data.

Full policy: https://sevagjb.github.io/TileMark/extension-privacy.html
```

- **Notes to reviewer:** see below.

### Notes to reviewer

Make a **new API key** for this review in the test TileMark (`tilemarktest.homeslab.nl`, account `testuser`), named *Firefox Add-ons review*, so you can remove it afterwards without touching the Edge or Chrome keys. Then paste:

```
This extension saves pages to the user's own self-hosted TileMark server (an open-source links app), so it needs a server address and an API key to work. A test server with a test account is ready:

TileMark address: https://tilemarktest.homeslab.nl
API key: <tm_…>
Sign in to see the saved links: username testuser / password <password>

Steps:
1. After installing, the settings page opens. Paste the address and the API key, press "Save and test" and allow access to that address when Firefox asks. It shows "Connected" and the number of groups found.
2. Open any web page and click the TileMark toolbar button. Pick a group, type a note, press Save: "Saved to <group>".
3. Press Save again on the same page: it says the page is already saved and in which group.
4. Right-click a link > "Save link to TileMark": the toolbar icon shows a check mark.
5. Open the TileMark address and sign in with the account above to see the saved links.

Host permissions are optional (optional_host_permissions) and requested at runtime for the one address the user enters; the extension never asks for all sites. No remote code, nothing minified or bundled: the zip is the source (https://github.com/sevagjb/TileMark/tree/main/extension). data_collection_permissions declares authenticationInfo and browsingActivity because the API key and the saved page's address go to the user's own TileMark server; nothing goes to the developer.
```

## After submitting

- **Pictures:** on the add-on's **Edit Product Page**, add the five screenshots from `store/` (1280×800) in the same order as for Chrome. The icon comes from the zip.
- **Review:** AMO signs the add-on after an automatic check, and a person may look at it as well. You get an email at each step. Keep the test TileMark and the review key until it's public, then remove the *Firefox Add-ons review* key.
- **Then:** add the listing link to the guide (`docs/browser-extension.md`), the README and the roadmap, as for Edge.
- **Updates:** upload the new `-firefox.zip` as a new version on the Developer Hub. The ID stays the same, so Firefox updates everyone by itself.
