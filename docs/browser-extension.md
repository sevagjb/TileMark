# Browser extension

The TileMark extension adds a **Save to TileMark** button to your browser's toolbar. One click on any page opens a small window with the page's title and address; pick a group, add a note if you like, and press **Save**. It also adds **Save page to TileMark** and **Save link to TileMark** to the right-click menu.

It works with your **own** TileMark: the extension stores nothing itself and talks only to the address you give it.

| | |
| --- | --- |
| Browsers | Microsoft Edge from its store; Chrome, Brave and Vivaldi from the zip for now (Chrome Web Store coming); Firefox 140 or later (Firefox Add-ons coming) |
| Needs | A TileMark you can reach from that browser, and an [API key](save-from-anywhere.md#api-key) |
| Languages | English, Nederlands, Deutsch, Français, Español, العربية |
| Privacy | See [Extension privacy](extension-privacy.md) |

> **Browser button or extension?** The [browser button](save-from-anywhere.md#browser-button) (a bookmark you drag to the bar) needs no installing, but needs you to be signed in to TileMark in that browser. The extension uses an API key instead, so it keeps working when your TileMark session has ended, and adds the right-click menu and a keyboard shortcut.

## Install

**Microsoft Edge:** install **[TileMark from Microsoft Edge Add-ons](https://microsoftedge.microsoft.com/addons/detail/tilemark/eaffnfpceclklbengpeihgembfgjbghi)** and press **Get**. Edge keeps it up to date by itself.

**Chrome, Brave, Vivaldi and other Chromium browsers:** the extension works there too; it is on its way to the Chrome Web Store. Until then, install it from the zip as below. A browser doesn't update an extension loaded this way, so load the new zip again after a new release.

**Firefox:** the extension is on its way to Firefox Add-ons. Firefox only keeps add-ons that Mozilla has signed, so until it's in the store you can only try it until Firefox restarts: download `tilemark-extension-<version>-firefox.zip` from the [releases on GitHub](https://github.com/sevagjb/TileMark/releases), open `about:debugging#/runtime/this-firefox`, press **Load Temporary Add-on…** and choose the zip. When installing, Firefox lists what the extension sends: your API key and the pages you save, both only to your own TileMark (see [Extension privacy](extension-privacy.md)).

**From the zip** (Edge, Chrome, Brave, Vivaldi, or to try a version before it's in the store): download `tilemark-extension-<version>.zip` (not the `-firefox` one) from the [releases on GitHub](https://github.com/sevagjb/TileMark/releases) and unzip it. Open the extensions page (`edge://extensions` in Edge, `chrome://extensions` in Chrome, `brave://extensions` in Brave, `vivaldi:extensions` in Vivaldi), turn on **Developer mode**, press **Load unpacked** and choose the unzipped folder.

## Connect it to your TileMark

The settings page opens by itself after installing. Later you find it with **⚙** in the extension's window, or by right-clicking the toolbar icon → **Extension options**.

1. In TileMark, open **👤 Your account → Save from anywhere** and press **Create API key**. Name it after this browser (for example *Edge on the laptop*) and copy the key (it is shown only once).
2. In the extension's settings, fill in:
   - **TileMark address**: the address you open TileMark at, for example `https://tilemark.example.com`. Typing just `192.168.1.20:8080` works too: an IP address, `localhost` or a name ending in `.local`, `.lan`, `.home` or `.internal` is taken as `http://`, anything else as `https://`.
   - **API key**: paste the key.
3. Press **Save and test**. The browser asks whether the extension may reach that one address; allow it. *Connected. Groups found: …* means it works.

> **Home Assistant app:** use TileMark's **own address** (its direct port), not the Home Assistant sidebar. The sidebar needs a Home Assistant sign-in that the extension doesn't have. See [TileMark's own address](home-assistant-add-on.md#tilemarks-own-address-optional).

> **One key per browser.** Since TileMark 2.11 an account can have several API keys. Give the extension in each browser its own key, separate from your iPhone Shortcut and scripts: removing one key in TileMark then stops only that browser, and the list in TileMark shows when each key was last used. With TileMark 2.10 or earlier there is one key per account, shared by everything that uses it.

## Saving

- **Toolbar button** (or **Alt+Shift+S**): the window shows the page's title (you can change it), its address, a **Group** list with the group you used last already chosen, and a **Note**. Choose **+ New group…** to make a group on the spot. **Ctrl+Enter** in the note saves.
- **Right-click** on a page → **Save page to TileMark**, or on a link → **Save link to TileMark**. This saves straight away, without the window, to the group set under **Right-click saves to** (by default the group you last used in the window). A mark on the toolbar icon shows how it went: **✓** saved, **=** already in TileMark, **!** something went wrong (hover over the icon to read what).
- **Already saved?** TileMark never keeps the same page twice. The window then says which group it is in. If the address only *looks* the same (another tracking code, `http` instead of `https`), **Save anyway** keeps both.

To change the keyboard shortcut, use **Change it** in the extension's settings (or open `edge://extensions/shortcuts`, or `chrome://extensions/shortcuts` in Chrome). In Firefox, **Change it** opens **Manage Extension Shortcuts** in `about:addons`.

## Settings

| Setting | What it does |
| --- | --- |
| TileMark address | Where links are sent. Changing it asks again for permission and drops the old one. |
| API key | Your key from TileMark. Kept in this browser only, never synced to other devices. |
| Right-click saves to | The group last used in the window (default), no group, or a fixed group. |
| Language | Same as the browser (default), or one of TileMark's languages. |
| Remove the address and key from this browser | Forgets everything the extension stored and gives back the permission. |

## When something doesn't work

| Message | What to do |
| --- | --- |
| Can't reach TileMark at … | Check the address, and that this computer can reach it (open it in a tab). |
| TileMark did not accept the API key | The key was removed in TileMark (or, before 2.11, replaced). Create a new one and paste it in the settings. |
| TileMark answered with a redirect | Something in front of TileMark sends the extension to a login page: an Authelia/Authentik/basic-auth rule on your reverse proxy, or the Home Assistant sidebar address. Use TileMark's own address, and let `/api/` through without that login (the API key protects it). |
| That address answered, but not like TileMark | The address points at something else. Use the address you open TileMark at. |
| TileMark refused this request | A proxy or firewall rule blocks the request, or the TileMark version is old. Let `/api/` through, or update TileMark. |
| The extension may not reach … yet | Open the settings and press **Save and test**, then allow access when the browser asks. |
| This page can't be saved | Only web pages (`http` and `https`) can be saved, not the browser's own pages such as `edge://`, `chrome://`, `about:` or the new-tab page. |
