# Home Assistant add-on

TileMark also runs as a Home Assistant add-on: your links get their own page in the Home Assistant sidebar, and everyone signs in with their Home Assistant account. It is the same app as the Docker version, with the same features.

The add-on needs **Home Assistant OS** or a **Supervised** installation. With Home Assistant Container or Core there are no add-ons; use [Docker](getting-started.md) instead.

## Install

[![Add repository to my Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fsevagjb%2Ftilemark)

Click the button above, or add the repository by hand:

1. In Home Assistant, go to **Settings → Add-ons → Add-on store**.
2. Open the **⋮** menu (top right) → **Repositories**, add `https://github.com/sevagjb/tilemark` and close the window.
3. Find **TileMark** in the store and press **Install**.
4. Turn on **Show in sidebar** and press **Start**.
5. Open **TileMark** from the sidebar.

There is no setup code and no separate password: Home Assistant has already signed you in.

## Accounts

- Every Home Assistant user who opens TileMark gets **their own TileMark account**, with their own links, groups and settings. Nobody, the admin included, can see someone else's links.
- The **first person** to open TileMark becomes its admin, and so does every **Home Assistant administrator**.
- Two-factor sign-in is not asked in the sidebar: Home Assistant's own sign-in, and its two-factor if you use it, already protects it.

## TileMark's own address (optional)

Inside the sidebar the address changes every session. Three features need a fixed address: the **browser button**, the **phone app** and the **API key**. To use them:

1. In the add-on, go to **Configuration → Network**, enter a port for TileMark (for example `8080`) and restart the add-on.
2. In TileMark (from the sidebar), open **⚙ Settings → Your account** and **set a password**. Accounts made through Home Assistant have none until you set one.
3. Open `http://<your-home-assistant>:<port>` and sign in with your TileMark username and that password.
4. Set up the browser button, the phone app or the API key from that page. See [Save from anywhere](save-from-anywhere.md).

Leave the port empty if you only use the sidebar. TileMark can then only be reached through Home Assistant. For the phone app the address must be HTTPS, for example through a reverse proxy.

## Backups

Everything TileMark stores is in the add-on's data folder, so **Home Assistant backups include TileMark**. The add-on pauses for a moment while Home Assistant makes a backup, so the copy is always consistent.

TileMark's own daily backup is **off** in the add-on, because Home Assistant already covers it, and Home Assistant can encrypt its backups itself. You can switch TileMark's on in **⚙ Settings → Installation** if you want both, and encrypt them as well.

Each person can always download a backup of their own links. It is encrypted with their TileMark password; accounts made by Home Assistant have none until they set one in **Your account**, so until then use **More options → A different password**. See [Backups](backups.md).

## Sensors and notifications

If Home Assistant has an MQTT broker (for example the **Mosquitto broker** add-on with the **MQTT** integration), TileMark shows up by itself as a device called **TileMark (Home Assistant)**:

- sensors for the number of **links** and **broken links**, and the time of the **last link check**;
- an **event** when the weekly link check finishes, for a notification;
- a **Visit** link on the device page that opens TileMark in the sidebar.

No setup is needed: the add-on uses Home Assistant's own broker. Details, and an example notification, are in [Home Assistant sensors](home-assistant-sensors.md).

## Moving from Docker to the add-on

1. In your Docker TileMark, each person downloads a backup: **⚙ Settings → Backup and restore → Download backup**.
2. In the add-on, each person opens TileMark from the sidebar once (this creates their account) and restores their file in the same section.

If you keep both running, give one of them a new device ID so Home Assistant shows them as two devices; see [Several TileMarks](home-assistant-sensors.md#several-tilemarks-in-one-home-assistant).

## Updating

Home Assistant shows an update for TileMark like for any add-on. If a new version doesn't appear yet, open the **Add-on store → ⋮ → Check for updates**. What changed is shown in the add-on's **Changelog** tab.

## Local addresses

TileMark does not fetch titles and pictures for addresses inside your network (`192.168.x.x`, `homeassistant.local` …) unless the admin allows it. Local links can always be saved. See [Accounts and security](accounts-and-security.md#local-addresses).
