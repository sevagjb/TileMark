# Changelog

## 2.12.0 (unreleased)

A new look: a second style, Workshop, a layout made for phones, and room to fit TileMark to your screen. Nothing needs to be done after updating; everything looks as before until you choose otherwise.

### New
- **Workshop style.** **👤 Your account → Appearance** now has **Style** (**Classic** or **Workshop**) and **Mode** (**Light**, **Dark** or **Follow my device**). Workshop is cream with warm charcoal in dark mode, orange buttons with dark text, and teal for the selected group and focus rings. *Follow my device* works for both styles. The TileMark logo stays blue in every style. The style is saved with your account.
- **Full width.** **👤 Your account → Cards and tile size → Full width** lets TileMark use the whole screen instead of a centred page of at most 1500 pixels. Remembered on each device.
- **Compact.** In the same card: less space around groups, cards and rows, so more fits on the screen; the text keeps its size. Remembered on each device.
- **Phones: a Groups button.** It replaces the row of groups you had to swipe. It shows the open group, its number of links and how many groups you have; tap it for all your groups and lists in a sheet from the bottom of the screen. Close it by tapping beside it or swiping its handle down. In the **Sections** layout, where phones had no group list at all, it's called **Jump to a group**: it scrolls straight to that group's section and unfolds it.
- **Phones: a round + button** at the bottom right (bottom left in Arabic) opens a small sheet with the link field and the group. The add field no longer takes a row at the top of the screen.

### Changed
- **The phone's status bar follows the style and mode.** It was always dark charcoal, even in light mode.
- **The selected group** has a bar in its own colour along its edge, so it's easier to spot.
- **Slim scrollbars** in the style's colours, instead of the system's wide ones with arrow buttons.
- **List rows in the Side panel layout** use their full width for the title. The card buttons appear over the end of the row when you point at it; before, 186 pixels at the end of every row were kept free for them. Touch screens wider than a phone, which show the buttons all the time, keep that room.
- **The page loads in your style straight away**, without a flash of the default colours first.
- **The `n` key on a phone with a keyboard** opens the + sheet.

### Fixed
- **The bookmark ribbon is back in the start screen's watermark logo.** It was left out by mistake in 2.8.0.

### Documentation
- **Keyboard shortcuts** in **Links and groups** are complete now: keys that work anywhere, keys in fields, moving around without a mouse, when the keys don't work, and the browser extension's keys.
- New sections **Width and spacing** and a rewritten **On a phone**, the new options in **Settings**, and two new questions in **Questions and troubleshooting** (the space beside the page, and the styles).
- The README now mentions the start screen, the four tile sizes, the iPhone Shortcut, and Delete all my links / Reset TileMark. The website's front page lists all six languages (French and Spanish were missing) and the backup sensor. The Home Assistant app's Documentation tab describes the keys and the phone layout fully.
- The roadmap lists every release again, including 2.4.1 to 2.4.6, 2.8.0 and 2.8.1.
- Since 2.11.0: clearer wording about API keys on the front page and in the own-address sections, and a link to **TileMark on Microsoft Edge Add-ons** in the guide and README.

## 2.11.0

Several API keys per account: one for each thing that saves links. Nothing needs to be done after updating; your current key keeps working.

### New
- **More than one API key.** **👤 Your account → Save from anywhere** now lists your API keys, and **Create API key** adds one next to the others instead of replacing it. Give each device or app its own key, for example *iPhone Shortcut* and *Edge on the laptop*. Every key does the same two things as before (add a link, read group names), at the same address with the same `Authorization: Bearer` header, so Shortcuts, scripts and the browser extension need no change.
- **Each key has a name, the first characters of the key, *last used* and the date it was made**, so you can see which ones are still in use. **Rename** changes the name; **Remove** switches off that one key, and the others keep working. Lost your phone? Remove its key and nothing else breaks.
- Up to 20 keys per account. A name is required and unique within your account.

### Changed
- **Your current key becomes the first key in the list, named *Default*.** It keeps working everywhere you use it. Because only a fingerprint of a key was ever stored, its first characters aren't known: the list shows *made before 2.11* for it. Rename it, or give each device a new key of its own and remove *Default* when nothing uses it any more. An installation backup made with an older version is upgraded the same way when it is restored.
- **Replace API key** and **Remove API key** are gone: create a new key and remove the old one instead.
- The API endpoints for managing keys are now `GET/POST /api/apikeys` and `PATCH/DELETE /api/apikeys/<id>` (used by TileMark's own page; the old `/api/apikey` is removed). Adding links and reading groups with a key are unchanged.
- The guide (**Save from anywhere**, **Browser extension**, **Settings**) explains several keys and suggests one key per browser for the extension.

## 2.10.0

The TileMark browser extension, starting with Microsoft Edge. Nothing needs to be done after updating TileMark itself.

### New
- **Browser extension** (version 1.0.0, in the `extension/` folder). A **Save to TileMark** button in the toolbar: the page's title, a group (the one you used last is already chosen, or make a new one), a note, **Save**. **Save page / Save link to TileMark** in the right-click menu saves straight away, and **Alt+Shift+S** opens the window. It says when a page is already in TileMark and in which group. It uses your **API key** (Your account → Save from anywhere), asks the browser for access to your TileMark's address only, and keeps the address and key in that browser only. In English, Dutch, German, French, Spanish and Arabic. See the new guide page **Browser extension** and its **privacy policy**.
- `scripts/build_extension.py` checks the extension (manifest, all six languages complete, every text present) and packs the zip for the store; the tests run the same checks.

### Changed
- **A request with an API key is judged by the key alone.** For the two things a key may do (add a link, read group names), TileMark now checks only the key when one is sent: the sign-in cookie is never used for it, and a wrong key gets *not valid* instead of falling back to the cookie. Such a request also no longer goes through the check for requests from other websites, which it doesn't need (a website can't send a key it doesn't know). Scripts and Shortcuts work as before.

## 2.9.1

### New
- **Admins pick from a list when sharing.** In a group's **✎ → Share with**, admins get the list of accounts as they type (or with the arrow in the field). Admins already see every account under **People**, so this shows them nothing new.
- **Show the list to everyone (admin setting, off by default).** **⚙ Settings → Installation → Show the list of accounts to everyone when sharing a group**. Off: everyone who isn't an admin types the exact username, as in 2.9.0, so the usernames on the server stay private. On: everyone picks from the list, handy in a household where everyone knows each other.

### Changed
- The README, the website's front page and the Home Assistant app's documentation now describe shared groups, and the guide explains the new setting in **Links and groups**, **Settings** and **Accounts and security**.

## 2.9.0

Shared groups: show a group to someone else on the same TileMark. Nothing needs to be done after updating; nothing is shared until you share it.

### New
- **Share a group.** Press **✎** next to a group, type the **exact username** of another account under **Share with** and press **Share**. They see the group under **Shared with me**, with your name next to it; your group shows **⇄**. **Stop sharing** in the same window makes it disappear from their TileMark straight away. Usernames are typed, not picked from a list, so nobody learns the other accounts on the server, and guessing many names is slowed down.
- **View only.** Someone a group is shared with can open, search and copy its links, but never add, edit, move or delete them: the group and its links stay the owner's. The server checks this on every request.
- **Your own favourites and Recently opened** on shared links: a ★ you give someone else's link is yours only, and the owner never sees it.
- **Copy to my links.** **⧉** on a shared card, or **ⓘ → Copy all** on a shared group, copies links into your own groups, with their title, note and picture. A copy is your own link and stays when the sharing ends. A page you already have is not copied twice, and TileMark says how many were left out.
- **Leave a group** that was shared with you: **ⓘ → Leave this group**.

### Backups and sharing
- **Your own backup never holds who a group is shared with.** A member's backup leaves out groups shared with them (those links are the owner's); an owner's backup holds the shared group's links, but not the people. A file can be restored on any server and into any account, so it never hands out access by itself.
- **Restoring your own backup on the same TileMark keeps sharing** for every group that comes back with the same name. Sharing of a group that isn't in the backup ends, and the restore message names those groups.
- **Restoring the whole installation brings sharing back exactly as it was**, because every account comes back with it.
- The guide has a new section, **Sharing a group**, and a table in **Backups** that explains each case.

## 2.8.1

### Changed
- **Extra small is a slim list in the Side panel layout.** One link per line, in rounded rows like the other sizes: the site's icon, the title, and the address on the right (plus the group in All links, Favourites and search results). On a computer every card button appears when you hover over a line; on a phone only ✎ is shown. In the Sections layout, Extra small stays a grid of small tiles.

## 2.8.0

A new look: a calm start screen, side panels instead of the Settings window, and a fourth tile size. Nothing needs to be done after updating.

### New
- **A clean start screen.** In the Side panel layout no group is open when TileMark starts: the TileMark logo shows faintly in the middle, with *Choose a group, or press / to search* and how many links, groups and favourites you have. **Click the open group again** (or press **Esc**) to close it and go back to this screen; this works for Favourites, All links and the other lists too. Prefer the old way? **👤 Your account → Start screen → Reopen the last group**.
- **Your account**, a new **👤** button next to ⚙. It holds everything that is yours: username and password, layout, appearance and language, cards and tile size, start screen, two-factor sign-in, passkeys, signed-in devices, save from anywhere, link check, your backup and restore, delete all my links, and Sign out.
- **Extra small tiles.** The tile size now has four steps: **Extra small**, **Small**, **Medium** and **Large** (**👤 Your account → Cards and tile size**). Extra small is a dense grid with only the site's icon and the title, for long lists; its only card button is ✎, whose window has favourite, group and delete.

### Changed
- **Side panels instead of a window in the middle.** Your account and Settings slide in from the right, just under the toolbar, and slide back when closed: with ✕, **Esc**, a click beside the panel, or the same button again. In Arabic they come from the left. Confirmations such as *Delete all my links* stay in the middle of the screen.
- **⚙ Settings is for admins only** and holds the installation's settings: People, Installation, Restore the whole installation, Home Assistant sensors and Reset TileMark. Other people no longer see the ⚙ button; everything they need is under 👤 Your account. As before, the server refuses admin changes from anyone who isn't an admin.
- **The tile size is remembered per device**, so a phone and a computer can each have their own. A new device starts with the size you chose last; after updating, every device keeps the size it had.
- The guide describes the start screen, the two panels and the tile sizes, with new pictures, and every path that moved now reads **👤 Your account → …**.

### Fixed
- On narrow phones (380 px or less) the import/export button is now the same size as the buttons next to it.

## 2.7.1

A hardening update: it finishes the security review that started with 2.6.1. Nothing changes in how you use TileMark, and nothing needs to be done after updating.

### Changed
- **TileMark runs as a normal user, not as root.** In Docker and Dockge, TileMark now runs as the user `tilemark` (id 1000), with no root rights left. The first start after updating gives the `data` folder to that user by itself; on the server its files then belong to user 1000. Set `PUID` and `PGID` to use another id, for example to match a folder on a NAS. On a network share that doesn't allow changing owners, TileMark keeps running as root, as before, and says so in the log. `docker exec tilemark python app.py reset-login` works as before.
- **Strict browser security rules.** TileMark's pages tell the browser to run only TileMark's own code (a Content-Security-Policy), to read files only as what they are (`nosniff`), and to show TileMark in a frame only on its own address. The Home Assistant sidebar keeps working as it is. A Webpage card on a Home Assistant dashboard that shows TileMark's Docker address now stays empty; add that Home Assistant address to the new `FRAME_ANCESTORS` container option to allow it.
- **Upload limits.** A picture for a card can be at most 20 MB (as before), an import 100 MB and a backup to restore 500 MB (before, up to 1 GB for everything). Only one import or restore larger than 25 MB is handled at a time. A file that is too large gets a clear message.
- **Only web picture formats.** Fetched and uploaded pictures are only opened as JPEG, PNG, WebP, GIF, ICO or AVIF; other, rarely used formats are refused.
- **Honest wording about admins.** Settings and the guide no longer say that nobody, the admin included, can see someone else's links. TileMark has no screen for it, but an admin can set a new password for an account and sign in with it, and the daily backups hold everyone's links. The new section *What an admin can do* in the guide explains this.

### Fixed
- **IPv6 addresses that stand for an IPv4 address** (NAT64 `64:ff9b::…` and 6to4 `2002:…`) are judged by that IPv4 address when TileMark fetches a page. A 6to4 address leading to the server itself or to a cloud metadata address is refused even when local addresses are allowed, and on an IPv6-only network with NAT64 ordinary sites get their titles and pictures again.

## 2.7.0

### New
- **Passkeys.** Sign in with your phone, computer or security key instead of typing your password: its face, fingerprint or PIN unlock proves it's you. Add one in **⚙ Settings → Passkeys** (your current password is asked first), then choose **🔑 Sign in with a passkey** on the sign-in page; no username is needed. A passkey counts as two-factor sign-in on its own, so no authenticator code is asked after it. Your password keeps working. Passkeys work on TileMark's HTTPS address with a name, not on an IP address or plain http (a browser rule); inside the Home Assistant sidebar they aren't used. Wrong passkey attempts count towards the same sign-in limits as wrong passwords.
- **Delete all my links**, in **⚙ Settings → Your account**: empties your own library (links, groups, pictures) for a fresh start. Your account, settings and passkeys stay. Asks for your password; **Download backup first** is right next to it.
- **Reset TileMark** (admin), the last card in Settings: deletes every account, link, picture and setting, so TileMark starts again as if just installed, and removes its device from Home Assistant. It asks you to type `RESET`, and for your password and two-factor code. A copy of everything is kept first and listed as **Before reset** under **Restore the whole installation**, so a reset can be undone; tick **Also delete every backup** for a completely clean start.
- **French (Français) and Spanish (Español).** The whole interface is now also in French and Spanish. The Language menu lists English, Nederlands, Deutsch, Français, Español, العربية.

### Changed
- The guide explains passkeys, Delete all my links and Reset TileMark (*Accounts and security*, *Settings*, *Backups*, FAQ).
- One new requirement for building the image: `webauthn` (py_webauthn), for checking passkeys.

## 2.6.1

A security update. Updating is recommended for everyone. **After updating, everyone signs in once more** (inside the Home Assistant sidebar nothing changes).

### Fixed
- **Restoring a backup only brings back web addresses.** A backup file made by hand could hold a `javascript:` address, which every other way of adding a link already refuses. Opening such a link could run someone else's code in TileMark, or inside Home Assistant when TileMark is opened from the sidebar. Restoring now checks every address the same way as adding a link, and skips anything that isn't `http://` or `https://`; local home-lab addresses are restored as before. TileMark's pages also refuse to open anything that isn't a web address.
- **A copy of a backup can no longer be used to sign in.** Daily backups held the key that signs sign-in cookies and the list of signed-in devices; with both, someone holding the file could sign in as an admin without a password. Backups now leave out that key, the signed-in devices and the MQTT broker password, and the devices are stored only as hashes, so no copy of the database can be turned into a sign-in. TileMark makes a new cookie key once with this update, so backups made before it open nothing either.
- **Requests from other websites are refused.** Another app on the same server (a different port) or on the same domain could make a signed-in browser add links, restore a backup or change settings in TileMark. Changes are now only accepted from TileMark's own pages. Shortcuts and scripts with an API key work as before.
- **A stranger can't lock you out behind a reverse proxy.** Behind a proxy, every visitor seems to come from the proxy's address, so 20 wrong passwords from anyone made everyone wait. Browsers that have signed in to an account before are now exempt for that account, so your own devices can always sign in.

### Changed
- **At most 10 wrong passwords or two-factor codes per account in 15 minutes**, wherever they come from, so guessing one account can't be spread over many addresses. Two sign-ins with the same two-factor code at the same moment can no longer both succeed.
- After restoring a daily backup in a **new** installation (copied by hand), enter the MQTT broker password again, as it is no longer part of backups.

## 2.6.0

### Changed
- **One file per language.** The translations moved out of the app's code into `pages/lang/`: one file per language (`nl.json`, `de.json`, `ar.json`) and a list of languages (`languages.json`) that the Language menu and the server both follow. English stays the base language. Adding a language is now one new file plus one line, with no code changes; see the new guide page **Translating TileMark**. `scripts/i18n_check.py` starts a new language and shows how far each one is translated.
- **Only the chosen language is sent to the browser**, together with the page's translation code, so more languages don't make TileMark heavier and nothing shows in English first.
- **The Language menu lists Arabic last:** English, Nederlands, Deutsch, العربية.
- **The sign-in page remembers the language** chosen on this browser; once you're signed in, your account's choice decides, as before. Choices made in 2.5 or earlier carry over by themselves.

### Fixed
- **Arabic counts use the right plural forms**: رابط واحد, رابطان, 3 روابط, 11 رابطًا, 100 رابط (also for devices, people, backups, minutes and hours ago, tabs, recovery codes and the "Try again in … seconds" message). Before, Arabic only had the English one-or-more choice.

## 2.5.0

### New
- **German (Deutsch).** The whole interface is now also in German: pick **Deutsch** in **⚙ Settings → Appearance → Language**, or let TileMark follow a browser set to German. Dates use the German format.

### Changed
- **A missing translation shows the English text.** If a text has no translation yet in the chosen language, TileMark shows it in English instead of leaving it empty. This makes it safe to add more languages step by step.

## 2.4.6

### Changed
- **An admin's "Check now" checks every account.** It works the same as the weekly check: it checks the links of all accounts, counts as that week's check, and Home Assistant's **Last link check** sensor and **Link check** event follow it. Before, it checked only the admin's own links and Home Assistant kept showing the last weekly check. "Check now" for other accounts still checks only their own links, and Home Assistant doesn't report it, so the sensor and the event always mean that all links were checked.

### Fixed
- **A connection problem no longer marks your links as broken.** When the machine TileMark runs on can't get online (no internet, or a VPN or firewall swallowing traffic), every link looked unreachable and was marked **Broken**. Now a check first makes sure TileMark can reach the internet; if it can't, the check stops, nothing changes, and **⚙ Settings → Link check** says why. The weekly check tries again later by itself. And when more than half of the links in a check of 10 or more can't be reached, TileMark takes that as a connection problem too and leaves those links as they were. A check that was stopped doesn't count as that week's check and isn't reported to Home Assistant.
- **"Visit" on the device page in Home Assistant opens TileMark in the sidebar.** In the Home Assistant app it used an old address that Home Assistant no longer knows, so it opened the default dashboard. The link is shown while **Show in sidebar** is on, on the app's Info tab.

## 2.4.5

### New
- **Two more entities in Home Assistant** (over MQTT), next to the link sensors:
  - **Last backup**: when the newest daily backup of the whole installation was made. It is empty while there is none, for example in the Home Assistant app, where daily backups are off unless you turn them on.
  - **Backup encryption**: on or off, following **⚙ Settings → Restore the whole installation**.
- They appear by themselves after the update; nothing needs to be set up again.

## 2.4.4

### Changed
- **"App" instead of "add-on".** Home Assistant calls add-ons *apps* since 2026.2. TileMark's Home Assistant page, the guide, the Settings hint for the direct port (English, Nederlands, العربية) and the device model in Home Assistant now say app. Menu paths point to **Settings → Apps → App store**. Web addresses of the guide pages stay the same.
- **Home Assistant app meets the current app standards.** The image carries the labels Home Assistant reads (type, version and architecture). The app's settings no longer use the outdated *watchdog* line: Home Assistant now restarts TileMark through the image's own health check, as before. Every change to the app is checked with the community app linter.
- The app's Documentation tab has a **License** section (MIT).

## 2.4.3

### Changed
- **The top bar on phones takes two rows, not three.** Search, the guide and Settings are small icon buttons beside the name, **Import** and **Export** share one button that opens a short menu with both names, and the add field has the row below. Search opens from the magnifier and closes again when it is empty. On a computer nothing changes: the buttons keep their names and search is always there.
- **The row under a group's name on phones** (sorting, refresh, Open all in tabs, Select) wraps to a second line when it doesn't fit; before, the last buttons ran off the screen.
- **The guide button** is a yellow light bulb now, in place of the question mark.

## 2.4.2

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
