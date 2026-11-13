# Changelog

## 1.2.0 (unreleased)

### New
- **Home Assistant add-on.** Add `https://github.com/sevagjb/linkboard` as an add-on repository and LinkBoard gets its own panel in the HA sidebar. Home Assistant signs people in: every HA user gets their own LinkBoard account on first visit (the first one and HA admins are admins). The direct port is off unless you set one. Data lives in the add-on folder, so HA backups include it.
- **Setup code.** A new installation prints a one-time code in the container log, and the welcome screen asks for it, so nobody else on the network can claim a fresh install. `docker exec linkboard python app.py setup-code` shows it again.
- **Daily backup** of the whole installation in `data/backups/`, last 7 kept (admin setting; off in the add-on, where HA backups cover it).
- **Card options** per account: picture size (small, medium, large), open links in a new tab or this tab, default group for new links.

### Changed
- All page addresses are relative, so LinkBoard works under a path prefix (needed for the HA sidebar). The browser button now uses the address LinkBoard is opened at.

### Fixed
- A wrong setup code no longer empties the password fields on the welcome screen.
- "Keep me signed in" no longer shows on the welcome screen, where it does nothing.

## 1.1.0

### New
- **Several accounts.** The first account is the admin and adds the others in **Settings → People**. Every account has its own links, groups, API key, backups and settings; nobody, the admin included, can see someone else's links.
- **No open installations.** A new installation shows a welcome screen that creates the first account before anything else is shown. "Turn off login" is gone.
- **Settings follow you.** Layout, appearance and sort order are stored with your account instead of per browser.
- **Safe fetching.** LinkBoard no longer fetches loopback, link-local or cloud-metadata addresses, and private network addresses only when the admin turns that on (**Settings → Installation**). Every redirect hop and the address actually connected to are checked. Very large pictures are refused.

### Changed
- `docker exec linkboard python app.py reset-login [username]` now prints a new password for that account (default: the first admin) instead of removing the login.
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
