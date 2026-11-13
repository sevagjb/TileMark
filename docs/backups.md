# Backups

TileMark has two kinds of backup. Use both, and your links are safe from a broken disk, a mistake or a bad update.

| | Your own backup | Daily backup of the installation |
| --- | --- | --- |
| **Holds** | Your links, groups, order, notes and pictures | Every account, with all links and settings |
| **Made by** | You, when you press **Download backup** | TileMark, automatically every day |
| **Stored** | Wherever you save the download | The `data/backups` folder on the server |
| **Encrypted** | With a password you choose (recommended) | Not yet (planned for 2.4) |
| **Restored by** | You, in **Backup and restore** | The admin, in **Restore the whole installation** |

## Your own backup

**⚙ Settings → Backup and restore**

1. Enter a **backup password**. This is optional but recommended: with a password, the file is encrypted (AES-256, with the key made from your password by scrypt) and saved as `.tmk`. Without one, it is a plain `.zip`.
2. Press **Download backup**.

Keep the password safe: **a forgotten backup password can't be recovered**, by you or anyone else.

A backup holds your links, groups, colours, order, notes, favourites and pictures. Accounts, passwords and API keys are never part of it.

### Restoring your own backup

1. In the same section, under **Restore**, choose the backup file.
2. Enter its password, if it has one.
3. Press **Restore from backup** and confirm.

This **replaces all your current links and groups** with those in the file. Other people's links are not touched, and neither is your account. It is all or nothing: a wrong password or a damaged file changes nothing.

You can restore into another TileMark, or another account. Older files work too, including backups from LinkBoard (TileMark's earlier name).

> Just want your links in another format? [Export](import-export.md#export) makes a readable TileMark or bookmarks file instead.

## Daily backups of the whole installation

Every day TileMark copies the whole installation (every account with its links and settings, and the pictures people uploaded themselves) into `data/backups/`. The **last 7** are kept. Fetched pictures are left out to keep the files small; they come back by themselves.

The admin can switch this off in **⚙ Settings → Installation → Keep a daily backup of the whole installation**. In the Home Assistant add-on it is off by default, because Home Assistant's own backups already include TileMark.

> **Copy them elsewhere.** A backup on the same disk doesn't survive a broken disk. Copy the `data/backups` folder to a NAS, another computer or cloud storage now and then, or let your server's backup tool include it.

## Restoring the whole installation (admin)

**⚙ Settings → Restore the whole installation** lists the daily backups, newest first, each with:

- **Download**, to keep a copy elsewhere;
- **Restore**, to put **every account** back to that day.

**Make a backup now** adds a fresh one, for example right before an update.

To restore:

1. Press **Restore** next to the day you want.
2. **Type the date** of that backup to confirm. This prevents restoring the wrong day by accident.
3. TileMark first saves a **safety copy** of how things are now (listed as *Before restore*; the last 3 are kept), then restores.
4. Everyone signs in again.

Changed your mind? Restore the safety copy, and you're back where you were.

A restore keeps how the installation connects to the outside: the [Home Assistant sensors](home-assistant-sensors.md) settings and the device in Home Assistant stay as they are.

## A complete copy by hand

With the container **stopped**, copying the whole `data` folder is a complete backup too. Put it back (with the container stopped) to restore everything exactly as it was.
