# TileMark

Your saved links, with thumbnails and groups, in the Home Assistant sidebar.

## Getting started

1. Start the add-on and turn on **Show in sidebar**.
2. Open **TileMark** from the sidebar. You are signed in with your Home Assistant account; there is no separate login.
3. Paste a link into the field at the top, or use **Import** to bring in your browser bookmarks.

## Accounts

Every Home Assistant user who opens TileMark gets their own TileMark account, with their own links, groups and settings. Nobody, the admin included, can see someone else's links.

- The first person to open TileMark becomes its admin, and so does every Home Assistant administrator.
- The admin can manage accounts and installation settings in TileMark's **⚙ Settings**.
- Already have TileMark in Docker? Make a backup there (**⚙ Settings → Backup**) and restore it here (**⚙ Settings → Restore**). Each person restores their own backup.

## TileMark's own address (optional)

Inside the sidebar the address changes every session. The **browser button**, the **phone app** and the **API key** need a fixed address, so for those:

1. In this add-on, go to **Configuration → Network** and enter a port for TileMark (for example `8080`), then restart the add-on.
2. In TileMark (from the sidebar), open **⚙ Settings → Your account** and set a password. Accounts made by Home Assistant have none until you set one.
3. Open `http://<your-home-assistant>:<port>` and sign in with your TileMark username and that password. Set up the browser button and the phone app from that page.

Leave the port empty if you only use the sidebar; then TileMark can only be reached through Home Assistant.

For the phone app (installing TileMark and sharing to it from other apps), that address must be HTTPS, for example through a reverse proxy.

## Backups

TileMark keeps everything in the add-on's data folder, so Home Assistant backups include it. The add-on stops for a moment while a backup is made, so the copy is always consistent.

TileMark's own daily backup is off in the add-on (Home Assistant's backups already cover it). Each person can still download a backup of their own links in **⚙ Settings → Backup**.

## Local addresses

To keep pages from making TileMark look inside your network, it does not fetch titles and pictures for local addresses (`192.168.x.x`, `homeassistant.local` …) unless the admin allows it in **⚙ Settings → Installation**. Local links can always be saved.

## Support

Questions and bug reports: <https://github.com/sevagjb/tilemark/issues>
