# Questions and troubleshooting

## General

**Is TileMark free?**
Yes. It is open source under the MIT licence, with no paid version, no tracking and no account anywhere.

**Does TileMark send my links anywhere?**
No. Your links stay on your own server. TileMark only visits the pages you save, to fetch their title and picture, and checks them once a week to find broken ones. The optional [Home Assistant sensors](home-assistant-sensors.md) send numbers only.

**How is this different from my browser's bookmarks?**
Your links have pictures, live in coloured groups, work in every browser and on every device, stay private per person, and get checked for broken pages. Your browser keeps working as before; [Import](import-export.md) copies your bookmarks in.

**Can my family use it too?**
Yes. The admin adds each person in **⚙ Settings → People**. Everyone gets their own private links. See [Accounts and security](accounts-and-security.md).

**Does it work on my phone?**
Yes, in any phone browser. With HTTPS you can also install it as an app, and on Android share links to it from other apps. See [Save from anywhere](save-from-anywhere.md#phone).

**Which languages?**
English, Dutch and Arabic. TileMark follows your browser's language; you can choose another in **⚙ Settings → Appearance**.

## Setting up

**Where is the setup code?**
In the container log: the stack's log in Dockge, or `docker logs tilemark`. Show it again with `docker exec tilemark python app.py setup-code`. In the Home Assistant app there is none: open TileMark from the sidebar.

**I forgot my password.**
Another admin can set a new one in **People**. If you are the only admin, run `docker exec tilemark python app.py reset-login` on the server. See [Forgot your password?](accounts-and-security.md#forgot-your-password)

**Are my backups encrypted?**
Your own backups are, with your login password. The daily backups of the whole installation are encrypted once an admin turns it on in **⚙ Settings → Restore the whole installation**. See [Backups](backups.md).

**I lost the recovery key.**
As long as an admin still knows their password, nothing is lost: make a new one with **New recovery key**.

**I lost the phone with my authenticator app.**
Sign in with one of your recovery codes, or ask an admin to use **People → Turn off 2FA**.

**Which version am I running?**
It is shown under the TileMark name at the top left, and at the bottom of Settings.

**How do I update?**
Dockge: **Update**. Docker: `docker compose pull && docker compose up -d`. Home Assistant: the app's update button. Your data is kept. See [Updating](getting-started.md#updating).

## Pictures and titles

**A card has no picture, only a letter.**
The site publishes no preview image, needs a sign-in (Instagram, for example), or blocks automated visits. Try **↻** on the card later, or set **your own picture**: **✎ → Picture**, or paste an image with Ctrl+V in the edit window.

**Links to my NAS or router have no picture.**
TileMark doesn't visit addresses inside your network unless the admin allows it in **⚙ Settings → Installation**. See [Local addresses](accounts-and-security.md#local-addresses).

**The title is wrong, or shows "Just a moment…".**
Some sites show a bot check instead of the page. TileMark recognises the common ones and keeps the address instead; set your own title with **✎** if needed.

**A big import is slow to fill in.**
Pictures are fetched a few at a time, so the server and the sites aren't overloaded. A few hundred links take a minute or two.

## Links

**A link shows "is blocked" or ERR_BLOCKED_BY_RESPONSE.**
Update TileMark: since 2.4.1, links opened from the Home Assistant sidebar open normally. Before, Home Assistant's sandboxed app frame was passed on to the new tab, and sites like YouTube refuse to load there. If it still happens on TileMark's own address, a browser extension is interfering; try a private window to confirm.

**I can't drag a card to reorder it.**
Reordering works inside one group, not in mixed lists like **All links**, **Favourites** or search results. Sorting must be on **My order**.

**TileMark says a link is already saved, but the address is different.**
They lead to the same page; TileMark ignores `www`, `https`, tracking parameters and redirects when comparing. See [Duplicates](import-export.md#duplicates). To save it anyway, use **Import** and tick it in the review.

**A working link is marked Broken.**
The site was unreachable twice during the last check. The label clears by itself when the next check (or **↻**) reaches it. See [Broken links](broken-links.md).

## Home Assistant

**The update doesn't show up in Home Assistant.**
Home Assistant checks for updates now and then. Force it: **Settings → Apps → App store → ⋮ → Check for updates**.

**The browser button or API key doesn't work in Home Assistant.**
They need TileMark's own address, not the sidebar. See [TileMark's own address](home-assistant-add-on.md#tilemarks-own-address-optional).

**I see only one TileMark device, but I run two.**
They share one device ID. Press **New ID** in one of them. See [Several TileMarks](home-assistant-sensors.md#several-tilemarks-in-one-home-assistant).

## Something else?

Ask a question or report a problem in the [issues](https://github.com/sevagjb/tilemark/issues). Mention your TileMark version (bottom of **⚙ Settings**) and whether you use Docker or Home Assistant.
