# Extension privacy

*Privacy policy of the TileMark browser extension. Last updated: 21 November 2026.*

The TileMark extension sends pages to **your own** TileMark server. It has no server of its own, and the developer receives nothing.

## What the extension sends, and where

When **you** press **Save** in its window, or choose **Save page to TileMark** or **Save link to TileMark** in the right-click menu, the extension sends to the TileMark address you entered in its settings:

- the address (URL) of the page or link,
- the page's title (only for a page, and you can change it first),
- the group you chose and the note you typed, if any,
- your API key, so TileMark knows which account the link belongs to.

To fill the **Group** list, it also asks that TileMark for your group names. Nothing is sent at any other moment: the extension does not watch your browsing, and it reads a page's address and title only when you press the button or use the menu on it.

## What the extension stores

In this browser only (the browser's local extension storage, never synced to other devices): your TileMark address, your API key, the group you used last, and your choices for the right-click group and the language. **Remove the address and key from this browser** in the settings, or uninstalling the extension, deletes all of it.

## What it does not do

- No analytics, tracking, advertising or crash reports.
- Nothing is sent to the developer or to any third party. What you save goes only to the TileMark server you chose, which is run by you (or whoever runs that TileMark).
- No selling or sharing of data, and no use for anything other than saving your links.

## Permissions

| Permission | Why |
| --- | --- |
| Active tab | Read the address and title of the page you're on, only when you press the button or the keyboard shortcut. |
| Context menus | The **Save page / Save link to TileMark** items in the right-click menu. |
| Storage | Keep your TileMark address, API key and choices in this browser. |
| Access to your TileMark's address | Send links to your TileMark. Asked for when you press **Save and test**, for that one address only; the extension does not ask for access to other websites. |

## The TileMark server

What happens to links after they arrive is up to the TileMark server you use. TileMark fetches each saved page once to get its title and picture. See the [TileMark guide](README.md) for how TileMark stores data and makes backups.

## Contact

Questions about this policy: open an issue in the [TileMark repository on GitHub](https://github.com/sevagjb/TileMark/issues).
