# Roadmap

What is planned next, and what each release brought. Changes per version in detail: [CHANGELOG.md](CHANGELOG.md).

## Next: 1.3.0

Small items plus two-factor sign-in, in one round.

- [ ] **Clean addresses when saving:** strip tracking parameters (`utm_*`, `fbclid`, `si` …) and recognise duplicates that only differ by `http`/`https`, `www` or a trailing slash.
- [ ] **Full JSON export and import:** keeps notes, favourites, order, colours and own pictures (the bookmarks file loses those).
- [ ] **Keyboard shortcuts:** `/` for search, `n` for a new link, Esc to clear.
- [ ] **Sign out other devices:** a list of active sessions in "Your account".
- [ ] **Two-factor sign-in (TOTP)** with an authenticator app, for accounts reached from outside the home network.

## Home Assistant add-on: tests on a real installation

Before the add-on goes from "experimental" to stable:

- [ ] A second Home Assistant user who is not an admin gets their own empty board, without the People and Installation sections.
- [ ] Direct port: set a port and a password, sign in at `http://<home-assistant>:<port>`, and the browser button and API key work there.
- [ ] A Home Assistant backup with LinkBoard in it restores cleanly.
- [ ] Optional: the watchdog starts LinkBoard again after it stops.
- [ ] **Promote the add-on to stable** (`stage` in `homeassistant-addon/config.yaml`).

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
- [x] "Save to LinkBoard" browser button and API key (3); install as a phone app with Share menu (4).
- [x] Favourites (5), notes (6), sort options per group (7), recently added and opened (8).
- [x] Broken-link check (9), own picture for a card (10), refresh for a selection, a group or everything (11).
