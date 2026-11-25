# Roadmap

What is planned next, and what each release brought. Changes per version in detail: [CHANGELOG.md](CHANGELOG.md).

## Next (medium)

- [ ] **Browser extension in more stores:** Chrome Web Store (listing ready in `extension/STORE-CHROME.md`; until then it installs from the zip in Chrome, Brave and Vivaldi), then Firefox Add-ons. Edge is live on [Microsoft Edge Add-ons](https://microsoftedge.microsoft.com/addons/detail/tilemark/eaffnfpceclklbengpeihgembfgjbghi) (see 2.10.0). Safari waits for an Apple developer account.
- [ ] **Shared groups, later steps** (after testing 2.9.0): a "may change" level next to view only (the database already has room for it), your own order for groups shared with you, and whether stopping a share should still remove its links from the other person straight away. (Notes on shared links stay visible to members, as decided in 2.9.0.)

## Parked (larger)

- [ ] **Tags on links**, next to groups.
- [ ] **Wider reach:** listings for Unraid, CasaOS and a Proxmox helper script.

## Other ideas, not planned

- Keep a readable copy of the page (12), so the text survives if the site goes away.
- Screenshot thumbnails for sites without a preview image (needs a headless browser; would make the image much larger).
- Desktop installer without Docker; Android app.
- Sync between two installations (for example the add-on and a Docker one), one-way mirror first. For now: use one installation from everywhere (the add-on's own port), or move links with Backup or Export and Import.

## Done

### 2.12.1
- [x] Phones: Select stays on the first row (icons for Open all, Collapse all and Expand all).
- [x] The sign-in page and the Save to TileMark window use the device's style and mode.

### 2.12.0
- [x] Workshop style next to Classic, each light, dark or following the device (Style + Mode); the logo stays blue.
- [x] Full width and Compact, remembered per device.
- [x] Phones: a Groups button with a sheet from the bottom (in Sections it jumps to a group), a round + button to add links, and the status bar in the style's colour.
- [x] Selected group marked with a bar in its colour, slim scrollbars, list rows with the full width for the title.
- [x] Complete keyboard shortcuts in the guide; README, website and roadmap brought up to date.

### 2.11.0
- [x] Several API keys per account (one per device or app), each with a name, last used, rename and remove; the old single key becomes "Default".

### 2.10.0
- [x] Browser extension for Microsoft Edge: toolbar window with group and note, right-click menu, keyboard shortcut, six languages; API-key requests are judged by the key alone.

### 2.9.1
- [x] Sharing: admins pick the username from a list; an admin setting shows the list to everyone (off by default).

### 2.9.0
- [x] Shared groups: share a group with another account by username, view only. Copy to my links, leave, personal favourites and Recently opened; sharing kept or left out of backups as explained in the guide.

### 2.8.1
- [x] Extra small as a slim list, one link per line, in the Side panel layout.

### 2.8.0
- [x] A clean start screen with the logo, close the open group by clicking it again; Your account and Settings as side panels; Extra small tiles; tile size per device.

### 2.7.1
- [x] Hardening: runs as a normal user instead of root, browser security rules (CSP, frames, `nosniff`), upload limits, web picture formats only, NAT64/6to4 addresses checked by their IPv4 address, and honest wording about what an admin can do.

### 2.7.0
- [x] Passkeys: sign in with your phone, computer or security key, without a password.
- [x] Delete all my links (per account) and Reset TileMark (admin), with a safety copy.
- [x] French and Spanish as fifth and sixth interface languages.

### 2.6.1
- [x] Security fixes: safe backup restore, no sign-in secrets in backups, protection against requests from other websites, and lockout protection behind a reverse proxy.

### 2.6.0
- [x] One file per language in `pages/lang/`, a language list for the menu, Arabic plural forms, and a guide for translators.

### 2.5.0
- [x] German as a fourth interface language, with English shown for any text not translated yet.

### 2.4.1 to 2.4.6
- [x] YouTube links open from the Home Assistant sidebar; passwords hidden while typing (2.4.1).
- [x] The version under the name, a guide button, Sign out always at hand (2.4.2).
- [x] Two-row top bar on phones, the light-bulb guide button (2.4.3).
- [x] "App" instead of "add-on" and the current Home Assistant app standards (2.4.4).
- [x] Last backup and Backup encryption entities in Home Assistant (2.4.5).
- [x] An admin's Check now checks every account (2.4.6).

### 2.4.0
- [x] Encrypted backups, unlocked with your login password: personal backups by default, daily backups when an admin turns it on, with a recovery key.

### 2.3.3
- [x] A complete Documentation tab in the Home Assistant add-on, with screenshots.

### 2.3.2
- [x] A complete guide with screenshots, and a website for it.
- [x] Settings: one card open at a time. Phone cards: buttons under the text.

### 2.3.1
- [x] Settings as collapsible cards with a status line each.
- [x] Home Assistant device name, Visit link and device ID, so several TileMarks can live side by side.

### 2.3.0
- [x] Interface languages (14): English, Dutch and Arabic, chosen by the browser or per account, with right-to-left layout for Arabic.

### 2.2.0
- [x] Home Assistant sensors and link-check event through MQTT discovery (add-on: Home Assistant's broker by itself).
- [x] Restore a daily backup of the whole installation from the admin settings, with a safety copy first.
- [x] Dialogs close with a click outside or Esc.

### 2.1.0
- [x] Clean addresses (tracking parameters removed) and duplicates recognised across `http`/`https`, `www`, trailing slash, parameter order, YouTube short forms and redirects.
- [x] Import review: duplicates from an import are listed, can be downloaded or kept, and are never dropped silently.
- [x] Duplicates list for links already saved: keep one, take over details from the others, remove the rest.
- [x] Full JSON export and import (TileMark file).
- [x] Keyboard shortcuts.
- [x] Signed-in devices with "sign out other devices".
- [x] Two-factor sign-in (TOTP) with recovery codes.

### 2.0.0
- [x] LinkBoard renamed to TileMark everywhere (clean break: fresh install, then restore the old backup).
- [x] Home Assistant add-on tested on a real installation (separate accounts, non-admin user, direct port, HA backup and restore, updates) and marked stable.

### 1.2.1
- [x] Titles of bot-check and consent screens are no longer saved.
- [x] Health check: Docker/Dockge show an unhealthy container, and Home Assistant's watchdog restarts the add-on.
- [x] Add-on release notes shown in Home Assistant; a release is just publishing the tag (the add-on version follows by itself).

### 1.2.0
- [x] Home Assistant add-on with a sidebar panel and Home Assistant sign-in; every HA user gets their own account.
- [x] One-time setup code for a new installation.
- [x] Daily backup of the whole installation, last 7 kept.
- [x] Card options: picture size, open in the same or a new tab, default group.

### 1.1.0
- [x] Several accounts (13): the first is the admin, who adds the others; links, groups, settings, API key and backups are private per account.
- [x] A new installation asks for the first account before showing anything (no open mode).
- [x] Safe fetching: no loopback, link-local or metadata addresses; private addresses only when the admin allows it.
- [x] Layout, appearance and sort order saved per account on the server.
- [x] Image tags: `edge` for every change on `main`, `latest` only for releases. Automated tests before every build.

### 1.0.0
- [x] Backup and restore, optionally encrypted (1).
- [x] Ready-made Docker image for PC and ARM servers, on GitHub's registry (2).
- [x] "Save to TileMark" browser button and API key (3); install as a phone app with Share menu (4).
- [x] Favourites (5), notes (6), sort options per group (7), recently added and opened (8).
- [x] Broken-link check (9), own picture for a card (10), refresh for a selection, a group or everything (11).
