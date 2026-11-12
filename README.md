# LinkBoard

A very small self-hosted page for your web links. Paste a link, and it shows up as a card with a thumbnail. Everything lives on one page, organised in coloured groups, like browser tab groups that you can open from any device.

## Features

- **Add a link by pasting it.** Title, description and thumbnail are fetched automatically.
- **Thumbnails** come from the page's preview image (for YouTube, Vimeo and TikTok from their official embed info), falling back to the site icon, then to a letter tile. They are stored locally, so the page stays fast.
- **Groups** with colours. In the default layout they are listed in a column on the left: click a group and its links appear beside it as a compact list, one under the other. Drag a card onto a group to move it, and use "Open all in tabs" to open a whole group at once.
- **Import everything in one go:** paste a list of links, or upload a bookmarks/favorites export from Edge, Chrome or Firefox. Folders become groups, duplicates are skipped.
- **Export** to a standard bookmarks file that can be imported back here or into any browser.
- **Your own group order.** Drag a group onto another group in the left column to move it, or pick a position in the group's edit dialog.
- **Settings** (⚙): choose the layout (side panel, or all groups as collapsible sections with large cards) and light/dark appearance. Saved per browser.
- **Search** across titles, addresses and groups.
- Light and dark mode, follows your system.
- **Optional login** with username and password.
- One container, one SQLite file. No external services.

## Run with Docker Compose / Dockge

In Dockge, create a new stack (for example `linkboard`), paste this and deploy:

```yaml
services:
  linkboard:
    image: ghcr.io/sevagjb/linkboard:latest
    container_name: linkboard
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
```

Then open `http://<your-server>:8080`.

All data (database and thumbnails) is kept in the `data` folder next to the compose file. Back up that folder and you have everything.

### Build from source

```bash
git clone https://github.com/sevagjb/linkboard.git
cd linkboard
docker build -t linkboard .
docker run -d --name linkboard -p 8080:8080 -v ./data:/data linkboard
```

Or change `image:` to `build: .` in `compose.yaml` and run `docker compose up -d --build`.

## Importing your Edge favorites

1. In Edge: Favorites → `…` → **Export favorites**. This saves an `.html` file.
2. In LinkBoard: **Import** → choose that file → **Import**.

Each folder becomes a group. Thumbnails are fetched in the background, a few at a time, so a big import fills in over a minute or two.

You can also paste a plain list of links (one per line) into the import box, or paste several lines straight into the "add" field.

## Login

Settings (⚙) → **Login** lets you set a username and password. Once it is on:

- Every page, the links, thumbnails, import and export all require signing in.
- "Keep me signed in" remembers a device for 30 days; **Sign out** is in Settings.
- Changing the login signs out every other device.
- After five wrong attempts, further tries from that address have to wait (15 seconds, doubling up to 5 minutes).
- The password is stored only as a salted hash.

Forgot the password? Remove the login from the server, then set a new one in Settings:

```bash
docker exec linkboard python app.py reset-login
```

LinkBoard itself speaks plain HTTP. On a home network that keeps other people out of the page, but the password is not encrypted in transit; put a reverse proxy with HTTPS in front if you need that, or if you expose it outside your network.

## Settings

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATA_DIR` | `/data` | Where the database and thumbnails are stored |
| `FETCH_WORKERS` | `4` | How many pages are fetched at the same time |
| `BEHIND_PROXY` | off | Set to `1` when LinkBoard runs behind a reverse proxy (Nginx Proxy Manager, Traefik, Caddy …). It then trusts the proxy's forwarded headers for the visitor's address and https. Leave it off when the port is reachable directly. |

## Good to know

- **Login is off until you turn it on.** Open Settings (⚙) → Login, choose a username and password, and from then on nothing is visible without signing in. See [Login](#login).
- Thumbnails are the preview image a site publishes, not a screenshot. Sites without one (and most local services) show their icon or a letter instead. Use the ↻ button on a card to try again.
- Addresses typed without `http://` get `https://`, except local ones (`192.168.x.x`, `localhost`, `name.local`), which get `http://`.

## Development

```bash
pip install -r requirements.txt
DATA_DIR=./data python app.py
```

## License

MIT
