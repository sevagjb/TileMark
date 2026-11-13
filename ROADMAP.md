# Roadmap

What is planned next, and what each release brought. Changes per version in detail: [CHANGELOG.md](CHANGELOG.md).

## Next: 2.4.0

- [ ] **Encrypted backups, unlocked with your login password.** Daily backups of the whole installation and the safety copy before a restore are encrypted automatically, with no extra password: an admin's login password (or a recovery key shown once) opens them, also on a new machine. Personal backup downloads are encrypted with your login password by default. Older unencrypted backups can still be restored.

## Later (medium)

- [ ] **Shared groups:** share a group with another account, read-only or editable.

## Parked (larger)

- [ ] **Tags on links**, next to groups.
- [ ] **Wider reach:** listings for Unraid, CasaOS and a Proxmox helper script, and a real browser extension with a toolbar icon.

## Other ideas, not planned

- Keep a readable copy of the page (12), so the text survives if the site goes away.
- Screenshot thumbnails for sites without a preview image (needs a headless browser; would make the image much larger).
- Desktop installer without Docker; Android app.

## Done

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
