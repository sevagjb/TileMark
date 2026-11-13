# Changelog

## 2.0.0 (unreleased)

### LinkBoard is now TileMark
- New name everywhere: the app, the container image (`ghcr.io/sevagjb/tilemark`), the repository (`sevagjb/TileMark`), the Home Assistant add-on (slug `tilemark`), commands (`docker exec tilemark …`), settings (`TILEMARK_*`), the database file and the backup format.
- This is a clean break, not an upgrade: install TileMark fresh and restore your LinkBoard backup in **Settings → Restore**. LinkBoard backup files (`.lbk` and `.zip`) are accepted, encrypted or not.
- Signing in, browser settings and API keys start fresh with the new installation.
- The Home Assistant add-on is now marked stable.

## 1.2.1

### Fixed
- Titles from bot-check and consent screens ("Just a moment…", "One moment, please…", "Security Check", Cloudflare's "Attention Required") are no longer saved as a link's title. The old title is kept, or the site name is shown. Links that already have such a title are fetched again once after the update.

### New
- Health check: `/healthz` answers when TileMark and its database work. Docker (and Dockge) show the container as unhealthy when it stops answering, and the Home Assistant add-on is restarted by HA's watchdog.
- The add-on shows these release notes when Home Assistant offers an update.

### Release process
- Publishing a `v*` tag is the whole release: after the image is built and pushed, the workflow sets the add-on's version and copies this changelog into the add-on folder, so Home Assistant only offers versions whose image exists.

## 1.2.0

### New
- **Home Assistant add-on.** Add `https://github.com/sevagjb/tilemark` as an add-on repository and TileMark gets its own panel in the HA sidebar. Home Assistant signs people in: every HA user gets their own TileMark account on first visit (the first one and HA admins are admins). The direct port is off unless you set one. Data lives in the add-on folder, so HA backups include it.
- **Setup code.** A new installation prints a one-time code in the container log, and the welcome screen asks for it, so nobody else on the network can claim a fresh install. `docker exec tilemark python app.py setup-code` shows it again.
- **Daily backup** of the whole installation in `data/backups/`, last 7 kept (admin setting; off in the add-on, where HA backups cover it).
- **Card options** per account: picture size (small, medium, large), open links in a new tab or this tab, default group for new links.

### Changed
- All page addresses are relative, so TileMark works under a path prefix (needed for the HA sidebar). The browser button now uses the address TileMark is opened at.

### Fixed
- A wrong setup code no longer empties the password fields on the welcome screen.
- "Keep me signed in" no longer shows on the welcome screen, where it does nothing.

## 1.1.0

### New
- **Several accounts.** The first account is the admin and adds the others in **Settings → People**. Every account has its own links, groups, API key, backups and settings; nobody, the admin included, can see someone else's links.
- **No open installations.** A new installation shows a welcome screen that creates the first account before anything else is shown. "Turn off login" is gone.
- **Settings follow you.** Layout, appearance and sort order are stored with your account instead of per browser.
- **Safe fetching.** TileMark no longer fetches loopback, link-local or cloud-metadata addresses, and private network addresses only when the admin turns that on (**Settings → Installation**). Every redirect hop and the address actually connected to are checked. Very large pictures are refused.

### Changed
- `docker exec tilemark python app.py reset-login [username]` now prints a new password for that account (default: the first admin) instead of removing the login.
- The weekly link check is an admin setting; **Check now** checks only your own links. Local addresses are skipped while local fetching is off, so they are never marked broken.
- Backups contain one account's links. Restoring replaces only your own links. Backups from 1.0 restore fine.
- Image tags: `latest` now moves only with a release. Every change on `main` goes to `edge`.

### Upgrading from 1.0
- Make a backup first. The database upgrades itself on the first start.
- With a 1.0 login: that login becomes the admin and keeps all links and the API key. Every device signs in once more.
- Without a 1.0 login: the welcome screen creates the admin, who gets all existing links.
- Local links (`192.168.x.x`, `nas.local` …) keep their saved title and picture, but are no longer refreshed until the admin turns on local fetching.

## 1.0.0
- First release.
