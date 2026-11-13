<img src="docs/logo.png" width="72" alt="TileMark logo">

# TileMark

A small self-hosted home for your web links. Paste a link and it becomes a card with a thumbnail. Everything lives on one page, organised in coloured groups, a bit like browser tab groups that you can open from any device.

One container, one data folder, no external services.

![TileMark with groups on the left and the links of one group listed beside them](docs/side-panel.png)

<details>
<summary>The other layout: all groups as collapsible sections</summary>

![TileMark showing all groups as collapsible sections with large cards](docs/sections.png)

</details>

## Features

- **Paste a link to save it.** Title, description and thumbnail are fetched automatically.
- **Thumbnails** come from the page's preview image (for YouTube, Vimeo and TikTok from their official embed info), then the site icon, then a letter tile. They are stored locally, so the page stays fast.
- **Groups** with colours, in your own order. Click a group to see its links; drag a group onto another to reorder.
- **Two layouts**, switchable in Settings: groups in a side column with a compact list beside it, or all groups on one page as collapsible sections with large cards.
- **Your own link order.** Drag a card inside a group to rearrange it.
- **Select several links** and move or delete them together, or drag the whole selection onto a group.
- **Favourites:** star a link to keep it at the top of its group and in a Favourites list.
- **Notes** on a link, shown on the card and included in search.
- **Sort** a group by your own order, newest, oldest, name or site.
- **Recently added** and **Recently opened** lists.
- **Save from anywhere:** a browser button, the phone's Share menu (when installed as an app over HTTPS), or an API key for scripts.
- **Broken-link check:** once a week (or on demand) TileMark checks every link and lists the ones that no longer work.
- **Your own picture** for a card: upload or paste an image when a site offers none.
- **Refresh** titles and pictures for one link, a selection, a whole group or everything.
- **Share** a link from its card: the phone's share sheet where there is one, otherwise the address is copied.
- **Open all in tabs** for a whole group at once.
- **Import in one go:** paste a list of links, or upload a bookmarks/favorites export from Edge, Chrome or Firefox, or a TileMark file. Folders become groups.
- **Duplicates are caught, never dropped silently:** the same page saved twice (with or without `www`, `https`, a trailing slash, tracking parameters, or behind a redirect or short link) is recognised. An import lists them for you to download, keep or discard, and a **Duplicates** list helps clean up what you already have.
- **Clean addresses:** tracking parameters (`utm_…`, `fbclid`, YouTube's `si` …) are removed when a link is saved.
- **Export** to a TileMark file with everything (groups, colours, notes, favourites, own pictures), or to a standard bookmarks file that any browser can import.
- **Two-factor sign-in** with an authenticator app, optional per account, plus a list of signed-in devices you can sign out.
- **Keyboard shortcuts:** `/` to search, `n` to add a link, `Esc` to clear.
- **Backup and restore** from Settings, optionally encrypted with a password.
- **Accounts for everyone in the house:** each person has their own links, groups, settings, API key and backups. The first account is the admin and adds the others.
- **Never open by accident:** a new installation asks for the first account, protected by a one-time setup code from the container log.
- **Home Assistant add-on:** TileMark in the HA sidebar, signed in with your Home Assistant account.
- **Card options per account:** picture size, open links in a new or the same tab, and the default group for new links.
- **Daily backup** of the whole installation in the data folder, the last 7 kept.
- **Search** across titles, addresses and groups.
- **English, Dutch and Arabic:** follows the browser's language, or choose one per account in Settings. Arabic is shown right to left.
- Light and dark appearance.

## Install

TileMark runs in Docker (below) or as a [Home Assistant add-on](#home-assistant-add-on).

You need Docker with Compose. In [Dockge](https://github.com/louislam/dockge), create a new stack and paste the compose; with plain Docker, save it as `compose.yaml` in an empty folder and run `docker compose up -d`.

```yaml
services:
  tilemark:
    image: ghcr.io/sevagjb/tilemark:latest
    container_name: tilemark
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
```

Then open `http://<your-server>:8080`.

Everything TileMark stores (the database and the thumbnails) is in the `data` folder next to the compose file.

### First steps

1. Create the first account on the welcome screen. It is the admin. The screen asks for a **setup code**, printed in the container log: in Dockge open the stack's log, with plain Docker run `docker logs tilemark`. (`docker exec tilemark python app.py setup-code` shows it again.) The code only exists until the first account is made; it stops anyone else on your network from claiming a fresh installation before you do.
2. Paste a link into the field at the top and press Enter, or use **Import** to bring in your browser bookmarks.
3. Create groups with **+ New group** and drag cards onto them.
4. To give someone else their own TileMark, add them in **⚙ Settings → People**.

### Update

In Dockge press **Update**. With plain Docker:

```bash
docker compose pull && docker compose up -d
```

Your data is kept.

Image tags: `latest` is the newest **release** and is what the compose above uses. `2.0.0` (or `2.0`) stays on one release. `edge` follows every change on `main` before it is released; use it only to try out what is coming.

**Coming from LinkBoard:** TileMark is the new name of LinkBoard, starting with 2.0.0. There is no in-place upgrade: install TileMark fresh (new image, new data folder) and restore your LinkBoard backup in **⚙ Settings → Restore**; old backup files, encrypted or not, are accepted.

## Home Assistant add-on

TileMark also runs as a Home Assistant add-on, with its own panel in the sidebar. It needs Home Assistant OS or a Supervised installation (with HA Container or Core, use Docker as above).

[![Add repository to my Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fsevagjb%2Ftilemark)

Or by hand: **Settings → Add-ons → Add-on store → ⋮ → Repositories**, add `https://github.com/sevagjb/tilemark`, then install **TileMark** and turn on **Show in sidebar**.

- **No second login:** Home Assistant tells TileMark who is signed in. Every HA user gets their own TileMark account on first visit; the first one and all HA admins are TileMark admins.
- **Backups:** everything is in the add-on's data folder, so Home Assistant backups include TileMark.
- **Browser button, phone app, API key:** these need a fixed address. Enter a port under the add-on's **Configuration → Network**, set a password in TileMark's **⚙ Settings → Your account**, and use `http://<your-home-assistant>:<port>`. Leave the port empty to reach TileMark only through Home Assistant.
- **Moving from Docker:** make a backup in your Docker TileMark and restore it in the add-on (each person their own).

The add-on uses the same image as the Docker install. Details: [homeassistant-addon/DOCS.md](homeassistant-addon/DOCS.md).

### Build from source instead

Replace the `image:` line with these two, and Docker builds the latest code from this repository on every deploy:

```yaml
    build: https://github.com/sevagjb/tilemark.git#main
    pull_policy: build
```

## Importing browser bookmarks

1. Export from the browser. In Edge: Favorites → `…` → **Export favorites**. In Chrome: Bookmark manager → `⋮` → **Export bookmarks**. Both save an `.html` file.
2. In TileMark: **Import** → choose that file → **Import**.

Each folder becomes a group. Thumbnails are fetched in the background, a few at a time, so a big import fills in over a minute or two.

You can also paste a plain list of links (one per line) into the import box, or paste several lines straight into the "add" field.

**Duplicates.** Links you already have are not added again, and they are not thrown away silently either: after the import a list shows each one next to the link it matches (or "earlier in this import"). From there you can download them as a TileMark or bookmarks file, tick the ones to keep as separate links anyway, and discard the rest. Two addresses count as the same page when they only differ by `http`/`https`, `www`, a trailing slash, the order of their parameters or tracking parameters, when one is a YouTube short form of the other (`youtu.be/…`, `/shorts/…`), or when one redirects to the other.

The **Duplicates** button (and entry in the left column) appears when your saved links contain such pairs. For each set you choose the link to keep; it can take over notes, the favourite star, an own title and picture from the others, which are then removed. "These are different" hides a set for good, and every set can be downloaded first.

## Export

**Export** offers two files:

- **TileMark file (`.json`):** everything, including groups and their colours, order, notes, favourites, dates and your own pictures. Import it into TileMark (this one or another, any account) to get it all back. Fetched thumbnails are left out; they come back by themselves.
- **Bookmarks file (`.html`):** addresses, titles and groups as folders, for importing into Edge, Chrome or Firefox.

## Save from anywhere

**Browser button.** In **⚙ Settings → Save from anywhere**, drag **🔖 Save to TileMark** to your favorites bar. Clicking it on any page opens a small window where you pick the group, add an optional note and save. You need to be signed in to TileMark in that browser.

**Phone.** When TileMark runs on HTTPS, open it in the phone's browser and choose "Install app" or "Add to Home screen". On Android it then appears in the Share menu of other apps, so you can send a page or video straight to a group. iOS installs the app but does not offer web apps in its Share menu; use the API key with a Shortcut there.

**API key.** Create one in the same Settings section. Every account has its own key; links sent with it go to that account. It is shown once, and it can only add links and read group names:

```bash
curl -X POST https://tilemark.example.com/api/links \
  -H "Authorization: Bearer tm_your_key" -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "group_id": 3, "note": "read later"}'
```

`title`, `note` and the group are optional. The group can be given by name (`"group": "Videos"`, created if it does not exist yet) or by id (`group_id`); `GET /api/groups` with the same header lists the groups and their ids.

## Accounts and login

Every page, link, thumbnail, import, export and backup requires signing in. There is no open mode: a new installation shows a welcome screen that creates the first account, which is the admin.

- **⚙ Settings → Your account:** change your username or password (needs the current password). A new password signs out your other devices.
- **Two-factor sign-in** (optional, per account): in **Your account → Two-factor sign-in → Turn on**, scan the QR code with an authenticator app (Google Authenticator, Microsoft Authenticator, 1Password, Aegis …) and confirm one code. From then on TileMark asks for a code after the password. You get ten single-use **recovery codes** for when the phone is not at hand; save them. A code is accepted only once. Inside the Home Assistant sidebar no code is asked: Home Assistant's own sign-in (and its two-factor, if you use it) applies there.
- **Signed-in devices:** **Your account** lists every device signed in on TileMark's own address, with browser, address and when it was last active. Sign out any of them, or all others at once.
- **⚙ Settings → People** (admin only): add people, give them a new password, make them admin or remove them (with all their links). There is no public sign-up page; only an admin adds accounts.
- Links are private per account. The admin manages accounts but cannot see anyone else's links.
- Layout, appearance and sort order are saved with the account, so they are the same on every device.
- "Keep me signed in" remembers a device for 30 days; **Sign out** is in Settings.
- After five wrong attempts, further tries from that address have to wait (15 seconds, doubling up to 5 minutes).
- Passwords are stored only as salted hashes.

Lost the phone with the authenticator app? Sign in with a recovery code, or ask an admin: **People → Turn off 2FA**. Forgot a password? This gives the first admin (or the account you name) a new random password, turns off their two-factor sign-in, signs out their devices, and prints the password:

```bash
docker exec tilemark python app.py reset-login
docker exec tilemark python app.py reset-login bob
```

## Backup and restore

**⚙ Settings → Backup** downloads a single file with all *your* links, groups, colours, order and thumbnails. Each person makes their own backup.

- With a password the file is encrypted (AES-256-GCM, key derived from the password with scrypt) and saved as `.tmk`. A forgotten backup password cannot be recovered.
- Without a password it is a plain `.zip`.
- Accounts, passwords and API keys are never part of a backup.

**⚙ Settings → Restore** replaces all your links and groups with the contents of a backup file; other people's links are not touched. Backups made with LinkBoard (TileMark's earlier name) work too. It is all-or-nothing: a wrong password or a damaged file changes nothing.

For the whole installation (all accounts), TileMark keeps a **daily backup** in `data/backups/`, the last 7 days (the admin can switch it off under **⚙ Settings → Installation**). It holds the database with every account and the pictures people uploaded themselves; fetched thumbnails are left out to keep it small and come back by themselves.

**⚙ Settings → Restore the whole installation** (admin) lists these backups with **Download** and **Restore**, and has **Make a backup now**. Restoring puts every account back to that day; to confirm, you type the backup's date. Before anything changes, TileMark saves a **safety copy** of the current state (listed as "before restore", the last 3 kept), so a restore can itself be undone. Everyone signs in again afterwards. How the installation connects (the MQTT settings and its device in Home Assistant) is not changed by a restore.

Copying the whole `data` folder while the container is stopped works as a full backup too.

## Broken links

TileMark checks all links once a week and lists the ones that no longer work under **Broken links** in the left column; each also gets a "Broken" label on its card. **⚙ Settings → Link check** has a **Check now** button for your own links; the admin can switch the weekly check off under **Installation**.

A link counts as broken when its address cannot be reached on two tries, or the site answers that the page does not exist (404 or 410). Sign-in walls, bot blocks and temporary server errors are not counted, so a link is not flagged just because a site is picky. The label disappears when a later check or a refresh succeeds.

## Home Assistant sensors (MQTT)

TileMark can appear in Home Assistant as a device **TileMark**, set up by itself through MQTT discovery (no YAML):

- **Links** and **Broken links**: counts for all accounts together (only numbers; nobody's links leave TileMark).
- **Last link check**: when the weekly check last ran.
- **Link check** (event): fires when the weekly check finishes, with `checked`, `broken` and `new_broken`, for automations such as a notification.

Turn it on in **⚙ Settings → Home Assistant sensors** (admin): fill in your MQTT broker (the one Home Assistant's MQTT integration uses), and the status line shows when it is connected. In the **Home Assistant add-on** it is on by default and uses Home Assistant's own broker when the broker field is empty.

An automation for a phone notification could look like this:

```yaml
triggers:
  - trigger: state
    entity_id: event.tilemark_link_check
conditions:
  - condition: template
    value_template: "{{ trigger.to_state.attributes.new_broken | int(0) > 0 }}"
actions:
  - action: notify.mobile_app_your_phone
    data:
      message: "TileMark found {{ trigger.to_state.attributes.new_broken }} new broken links."
```

## Local addresses and safety

TileMark fetches pages to get titles and pictures, and the address of a picture comes from the page itself. To stop a page (or another account) from making TileMark look inside your network, it never fetches loopback, link-local or cloud-metadata addresses, and by default no private network addresses either (`192.168.x.x`, `10.x.x.x`, `nas.local` …). Redirects are checked hop by hop, and so is the address actually connected to.

You can still save local links; they show their address and a letter tile. If you want titles and pictures for them, and you trust everyone who has an account, the admin can turn on **⚙ Settings → Installation → Fetch titles and pictures for local network addresses**. The link check skips local addresses while this is off, so they are never reported as broken.

## HTTPS and reverse proxies

TileMark itself speaks plain HTTP. On a home network the login keeps other people out of the page, but the password is not encrypted in transit. For that, or for access from outside your network, put a reverse proxy with HTTPS in front (Nginx Proxy Manager, Traefik, Caddy …) and forward your hostname to `http://<your-server>:8080`.

Nothing needs to be configured in TileMark for this. The same compose file works for the local address, the HTTPS address, or both at once: TileMark reads the standard forwarded headers a proxy sends, gives HTTPS visitors an HTTPS-only login cookie, and limits wrong-password attempts per visitor either way.

## Options

Environment variables for the container:

| Variable | Default | Meaning |
| --- | --- | --- |
| `FETCH_WORKERS` | `4` | How many pages are fetched at the same time |
| `DATA_DIR` | `/data` | Where the database and thumbnails are stored |

Layout, appearance, sort order and the card options (picture size, open in a new or the same tab, default group for new links) are chosen in **⚙ Settings** and saved with your account.

## Good to know

- Thumbnails are the preview image a site publishes, not a screenshot. Sites without one, sites that require a login (Instagram, for example) and local services (see above) show their icon or a letter instead. Use ↻ on a card to try again.
- Addresses typed without `http://` get `https://`, except local ones (`192.168.x.x`, `localhost`, `name.local`), which get `http://`.
- Reordering by drag and drop works inside one group, not in "All links" or in search results.
- If a link to a large site (YouTube, Instagram …) will not open with a normal click but opens with right-click → "Open in new tab", a browser extension is interfering. Try a private window to confirm.

## Roadmap

Planned work is listed in [ROADMAP.md](ROADMAP.md). Ideas and bug reports are welcome in the [issues](https://github.com/sevagjb/tilemark/issues).

## Development

```bash
pip install -r requirements.txt
DATA_DIR=./data python app.py
pip install pytest pyyaml && pytest -q    # tests: upgrade, accounts kept apart, address checks, add-on sign-in
```

The app is a single Flask file (`app.py`) with a few static pages in `pages/`, and SQLite for storage. Changes per version are in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE)
