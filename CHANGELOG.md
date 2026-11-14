# Changelog

## 2.4.2 (unreleased)

### New
- **The version** is shown under the TileMark name at the top left, in both layouts, so you don't need to open Settings to see it.
- **?** button next to ⚙ opens the guide on the website.
- **Sign out** is at the bottom of Settings, always visible, next to **Done** (not shown in the Home Assistant sidebar, where Home Assistant's own sign-in applies).

### Changed
- Links added elsewhere (browser button, phone, API key, another device) show up when you come back to the TileMark tab, and otherwise every 5 minutes while it is open. Before, only after a reload.

## 2.4.1

### Fixed
- **YouTube links blocked in the Home Assistant sidebar.** A left click showed "www.youtube.com is blocked" (ERR_BLOCKED_BY_RESPONSE), while right-click → Open in new tab worked. Home Assistant shows add-ons in a sandboxed frame, a tab opened from it inherits the sandbox, and sites that send a Cross-Origin-Opener-Policy (YouTube, X …) refuse to load in a sandboxed tab. Tabs are now opened from Home Assistant's own page, which isn't sandboxed. On TileMark's own address nothing changes.
- **Open all in tabs** said "Your browser blocked N tabs" even when every tab opened.
- **Passwords are hidden while you type them.** The questions for a password (setting up encrypted backups, turning encryption on or off, a new recovery key, restoring an encrypted backup, two-factor sign-in, a new password for someone in People) used the browser's own box, which shows what is typed. They now use TileMark's own window, hidden by default. Every password field has a button to show what you typed.
- **Restoring a protected backup with no password** looked like nothing happened. The message was there, but behind the Settings window. Messages now always appear on top, and a missing password is said right away, next to the password field.

## 2.4.0

### New
- **Encrypted backups, without an extra password to remember.**
  - **Your own backup** is encrypted with your login password by default. Change your password later and both the old and the new one still open it. Under **More options**: a different password, or no encryption.
  - **Daily backups of the whole installation** can be encrypted by an admin (**⚙ Settings → Restore the whole installation → Turn on encryption**). Every admin opens them with their own password, and a **recovery key**, shown once, opens them when no password works, also on a brand-new installation.
  - Turning encryption on first lists the unencrypted backups that will be deleted (how many, and their dates) and asks you to confirm. A first encrypted backup is made right away.
  - A reset password gets access back when another admin signs in, or with the recovery key. **New recovery key** and **Turn off encryption** are in the same place.
- Older backups, encrypted or not, still restore.

### Fixed
- Home Assistant sensors: when TileMark reconnected (for example after **New ID**) while it was still announcing itself, a late "online" could land on the old device's topics after they were cleared.
## 2.3.3

### Changed
- **Home Assistant add-on: a complete Documentation tab.** It now explains every part of TileMark (saving links, groups, import, duplicates, broken links, settings, backups, sensors, TileMark's own address, troubleshooting) with screenshots, instead of a short summary. The Info tab got a picture and a feature list.

### Fixed
- The add-on's Info tab showed a broken picture after the screenshots moved. The add-on's pictures now point to the release they belong to, so they keep working when the guide changes.

## 2.3.2

### New
- **A new guide and website:** every feature and every option explained step by step, with screenshots, at <https://sevagjb.github.io/TileMark/> and in the `docs` folder. The README is now a short introduction with a quick start.

### Changed
- Settings: opening a card closes the one that was open, so only one is open at a time.
- On phones, the buttons on a card sit in a row under the text, so titles are no longer cut short.

### Fixed
- Messages about a single link no longer say "1 links" (import, duplicates, removing a person).

## 2.3.1

### New
- **Settings in cards:** every section opens and closes with a click on its title, and shows a short status while closed (for example "Two-factor sign-in: Off" or "Home Assistant sensors: Connected"). Open cards are remembered. Admin sections are grouped at the bottom.
- **Home Assistant sensors:** a device name you can set, a **Visit** link on the device page back to TileMark (for the add-on, its sidebar page), and the device ID with a **New ID** button.

### Fixed
- Two TileMarks made from the same database (for example the add-on and a Docker one) showed up in Home Assistant as one device and kept pushing each other off the MQTT broker. Each connection now has its own client name, and **New ID** separates the devices.

## 2.3.0

### New
- **Languages: English, Dutch and Arabic.** TileMark follows the browser's language; Settings → Appearance → Language sets one for your account, so all your devices use it. Arabic is shown right to left.
- Server messages (errors, link check, Home Assistant sensors status) and dates follow the chosen language.

## 2.2.0

### New
- **Home Assistant sensors over MQTT:** TileMark appears in Home Assistant as a device with sensors for links, broken links and the last weekly check, plus an event when that check finishes (with the number of newly broken links), set up by MQTT discovery. Settings → Home Assistant sensors; in the add-on it uses Home Assistant's broker by itself.
- **Restore the whole installation from a daily backup** in the admin settings, with Download, Restore and "Make a backup now". The admin types the backup's date to confirm, and a safety copy of the current state is made first, so a restore can be undone.
- The version number is shown at the bottom of Settings.

### Changed
- Dialogs (Settings, Export, Duplicates, editing) close with a click outside them or with Esc. The import review and Settings while recovery codes are shown stay open, so nothing is lost by accident.
- In the Home Assistant add-on, the start-up message for a new installation points to the sidebar instead of a setup code.

## 2.1.0

### New
- **Duplicates are caught.** Saving a page you already have tells you where it is. The same page counts even with or without `www`, `https`, a trailing slash, tracking parameters, in another parameter order, as a YouTube short form (`youtu.be`, `/shorts/`), or when one address redirects to the other.
- **Import review:** an import no longer drops duplicates silently. They are listed next to the link they match; download them (TileMark or bookmarks file), keep some as separate links, discard the rest.
- **Duplicates list** for links already saved: keep one per set and optionally take over notes, favourite, own title and picture from the others; "These are different" hides a set; every set can be downloaded first.
- **Clean addresses:** tracking parameters (`utm_…`, `fbclid`, `gclid`, YouTube's and Spotify's `si` …) are removed when a link is saved.
- **TileMark file:** Export → TileMark file (`.json`) keeps everything (groups and colours, order, notes, favourites, dates, own pictures); Import brings it all back.
- **Two-factor sign-in (TOTP)**, optional per account, with a QR code for any authenticator app and ten single-use recovery codes. Not asked inside the Home Assistant sidebar. Admins can turn it off for someone who lost their phone; `reset-login` turns it off too.
- **Signed-in devices** in Your account, with "Sign out" per device and "Sign out all other devices".
- **Keyboard shortcuts:** `/` search, `n` add a link, `Esc` clear the search or leave a field.

### Changed
- After updating, every device signs in once more (sign-ins are now kept on the server so they can be listed and signed out).

## 2.0.0

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
