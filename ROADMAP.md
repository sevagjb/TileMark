# Roadmap

What is planned next, and what each release brought. Changes per version in detail: [CHANGELOG.md](CHANGELOG.md).

## Next: 2.1.0

Small items plus two-factor sign-in, in one round.

- [ ] **Clean addresses when saving:** strip tracking parameters (`utm_*`, `fbclid`, `si` …) and recognise duplicates that only differ by `http`/`https`, `www` or a trailing slash.
- [ ] **Same page, different address:** use the address a link finally lands on (after redirects and short links such as `youtu.be/…` → `youtube.com/watch?v=…`) when checking for duplicates.
- [ ] **Duplicates from an import are reviewed, not dropped:** after an import, a list shows each duplicate next to the link already saved (title, group or folder, note). From there you can download them as a file (bookmarks or JSON) to keep a copy, keep one as a separate link where it really is different, and then remove the rest. Nothing is thrown away without being shown first.
- [ ] **Duplicates list for links already saved:** a "Duplicates" entry in the left column, like "Broken links", for near-duplicates already in the collection (for example from earlier imports). Same choices: download a copy, choose which one to keep (its note, favourite and own picture are kept, details from the other can be taken over), remove the others.
- [ ] **Full JSON export and import:** keeps notes, favourites, order, colours and own pictures (the bookmarks file loses those).
- [ ] **Keyboard shortcuts:** `/` for search, `n` for a new link, Esc to clear.
- [ ] **Sign out other devices:** a list of active sessions in "Your account".
- [ ] **Two-factor sign-in (TOTP)** with an authenticator app, for accounts reached from outside the home network.

## After that (medium)

- [ ] **Shared groups:** share a group with another account, read-only or editable.
- [ ] **Home Assistant integration:** sensors for the number of links and broken links, and a webhook or notification when the weekly check finds broken links.
- [ ] **Restore a daily backup from the admin settings**, instead of stopping the container and unzipping by hand.
- [ ] **Interface languages (14):** English, Dutch and Arabic, including right-to-left layout for Arabic.

## Parked (larger)

- [ ] **Tags on links**, next to groups.
- [ ] **Wider reach:** listings for Unraid, CasaOS and a Proxmox helper script, and a real browser extension with a toolbar icon.

## Other ideas, not planned

- Keep a readable copy of the page (12), so the text survives if the site goes away.
- Screenshot thumbnails for sites without a preview image (needs a headless browser; would make the image much larger).
- Desktop installer without Docker; Android app.

## Done

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
