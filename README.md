<p align="center">
  <img src="docs/logo.png" width="96" alt="TileMark logo">
</p>

<h1 align="center">TileMark</h1>

<p align="center">
  <b>Your web links, as picture tiles, on your own server.</b><br>
  Paste a link and it becomes a card with a picture. Sort your cards into coloured groups, open them from any device, and keep them private, for everyone in your home.
</p>

<p align="center">
  <a href="https://github.com/sevagjb/TileMark/releases/latest"><img alt="Latest release" src="https://img.shields.io/github/v/release/sevagjb/TileMark?label=release"></a>
  <a href="https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fsevagjb%2Ftilemark"><img alt="Home Assistant add-on" src="https://img.shields.io/badge/Home%20Assistant-add--on-18bcf2?logo=homeassistant&logoColor=white"></a>
  <a href="LICENSE"><img alt="MIT licence" src="https://img.shields.io/github/license/sevagjb/TileMark"></a>
</p>

<p align="center">
  <a href="#quick-start"><b>Quick start</b></a> ·
  <a href="https://sevagjb.github.io/TileMark/"><b>Website</b></a> ·
  <a href="docs/README.md"><b>Guide</b></a> ·
  <a href="docs/faq.md"><b>FAQ</b></a>
</p>

![TileMark with groups on the left and the links of one group beside them](docs/images/side-panel.webp)

## Why TileMark

- **Links you can see.** Every link gets the picture and title its site publishes, so you find things at a glance instead of reading a list of names.
- **Organised your way.** Coloured groups in your own order, favourites on top, notes on cards, and two layouts to choose from.
- **Everywhere you are.** One page in any browser, on any device. Save from a browser button, your phone's Share menu, or a script.
- **Yours, and private.** Runs on your own server with one container and one data folder. No cloud service, no tracking. Each person in your home gets their own private links, and backups are encrypted with your login password.
- **Tidy by itself.** Duplicates are recognised, tracking junk is stripped from addresses, and a weekly check finds links that stopped working.
- **At home in Home Assistant.** Install it as an add-on with its own sidebar page, and get sensors and notifications through MQTT.

## Features

<table>
<tr>
<td width="50%" valign="top">

**Saving and organising**
- Paste a link: title, description and picture are fetched for you
- Coloured groups, drag-and-drop order, favourites and notes
- Sort by your order, newest, oldest, name or site
- Select many links to move, refresh or delete together
- Search across titles, addresses, notes and groups
- Your own picture for any card (upload or paste)

</td>
<td width="50%" valign="top">

**Bringing links in and out**
- Import bookmarks from Edge, Chrome, Firefox, Brave or Safari
- Duplicates are listed for review, never dropped silently
- Export to a TileMark file or a browser bookmarks file
- Browser button, Android Share menu, and an API key
- Recently added and recently opened lists

</td>
</tr>
<tr>
<td valign="top">

**Safe and private**
- Accounts for everyone in the home, links private per person
- Two-factor sign-in with any authenticator app
- See and sign out your signed-in devices
- Encrypted backups, unlocked with your login password or a recovery key
- Never visits addresses inside your network unless you allow it

</td>
<td valign="top">

**Pleasant to use**
- Two layouts: side panel or large picture sections
- Light and dark, following your device
- English, Dutch and Arabic (right to left)
- Works on phones; installs as an app over HTTPS
- Keyboard shortcuts: `/` search, `n` add, `Esc` clear

</td>
</tr>
</table>

## Quick start

### Docker (Dockge, Portainer, plain Docker)

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

1. Paste this into a new stack in Dockge, or save it as `compose.yaml` and run `docker compose up -d`.
2. Open `http://<your-server>:8080`.
3. Create the first account. The setup code it asks for is in the container log (`docker logs tilemark`).

Full walkthrough: [Getting started](docs/getting-started.md).

### Home Assistant add-on

[![Add repository to my Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fsevagjb%2Ftilemark)

Add the repository, install **TileMark**, turn on **Show in sidebar** and start it. You're signed in with your Home Assistant account. More: [Home Assistant add-on](docs/home-assistant-add-on.md).

## A closer look

<table>
<tr>
<td width="50%"><img src="docs/images/sections-dark.webp" alt="All groups as sections, in dark mode"><br><sub><b>Sections layout</b>, in dark mode</sub></td>
<td width="50%"><img src="docs/images/import-review.webp" alt="Reviewing duplicates after an import"><br><sub><b>Import review</b>: duplicates are listed, never lost</sub></td>
</tr>
<tr>
<td><img src="docs/images/settings.webp" alt="Settings as cards"><br><sub><b>Settings</b>: one card per topic, with its status</sub></td>
<td><img src="docs/images/arabic.webp" alt="TileMark in Arabic"><br><sub><b>Three languages</b>, including Arabic right to left</sub></td>
</tr>
</table>

## Guide

| | |
| --- | --- |
| [Getting started](docs/getting-started.md) | Install, first account, first links, updating, HTTPS |
| [Home Assistant add-on](docs/home-assistant-add-on.md) | Sidebar, accounts, own address, backups |
| [Links and groups](docs/links-and-groups.md) | Everything on the main page |
| [Import and export](docs/import-export.md) | Bookmarks in, files out, duplicates |
| [Save from anywhere](docs/save-from-anywhere.md) | Browser button, phone, API key |
| [Broken links](docs/broken-links.md) | The weekly check |
| [Accounts and security](docs/accounts-and-security.md) | People, two-factor sign-in, devices, passwords |
| [Backups](docs/backups.md) | Your own, daily, restoring |
| [Home Assistant sensors](docs/home-assistant-sensors.md) | Sensors and notifications over MQTT |
| [Settings](docs/settings.md) | Every option, card by card |
| [Questions and troubleshooting](docs/faq.md) | Common questions and fixes |

The same guide, as a website: **<https://sevagjb.github.io/TileMark/>**

## Roadmap and changes

What's coming next is in the [roadmap](ROADMAP.md); what changed in each version is in the [changelog](CHANGELOG.md). Ideas and bug reports are welcome in the [issues](https://github.com/sevagjb/tilemark/issues).

## Development

TileMark is a single Flask file (`app.py`) with a few static pages in `pages/`, and SQLite for storage.

```bash
pip install -r requirements.txt
DATA_DIR=./data python app.py                     # http://localhost:8080
pip install pytest pyyaml "amqtt==0.12.*" && pytest -q
```

The website is built from `docs/` with `python scripts/build_site.py` (output in `_site/`).

## Licence

[MIT](LICENSE)
