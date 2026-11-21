# Save from anywhere

You don't have to open TileMark to save a link. There are three ways to send a page to it from wherever you are, plus the [browser extension](browser-extension.md) for Edge.

| Way | Best for | Needs |
| --- | --- | --- |
| [Browser button](#browser-button) | Your computer | Being signed in to TileMark in that browser |
| [Phone app](#phone) | Android, from any app's Share menu | TileMark on an HTTPS address |
| [API key](#api-key) | Scripts, iPhone Shortcuts, automations | An API key from Your account |
| [Browser extension](browser-extension.md) | Edge: toolbar button, right-click menu, shortcut | An API key |

All three are found in **👤 Your account → Save from anywhere**. Links saved this way show up in an open TileMark tab as soon as you switch back to it.

> **Home Assistant app:** these need TileMark's own address, not the sidebar. See [TileMark's own address](home-assistant-add-on.md#tilemarks-own-address-optional).

## Browser button

1. Open **👤 Your account → Save from anywhere**.
2. **Drag** the **🔖 Save to TileMark** button onto your browser's favorites/bookmarks bar. (Clicking it in Settings does nothing; it only works from the bar.)
3. On any web page, click the button in your bar. A small window opens with the page's address and title filled in.
4. Pick a **group**, add a **note** if you like, and press **Save**.

It works in Edge, Chrome, Firefox, Brave and Safari. If the small window asks you to sign in, sign in once in that browser.

## Phone

When TileMark runs on **HTTPS** (see [Reaching TileMark from outside](getting-started.md#reaching-tilemark-from-outside-with-https)), you can install it as an app:

1. Open TileMark in your phone's browser and sign in.
2. Choose **Install app** or **Add to Home screen** from the browser menu.

TileMark then opens full-screen from its own icon, like an app.

**On Android**, it also appears in the **Share** menu of other apps. In YouTube, Chrome, Reddit or any app, tap **Share → TileMark**, pick a group and save.

**On iPhone and iPad**, iOS installs TileMark on the home screen but doesn't offer web apps in its Share menu. Use the API key with a Shortcut instead ([below](#iphone-shortcut)).

## API key

An API key lets a script, a Shortcut or an automation add links to **your** account. It can only **add links** and **read your group names**: it cannot read, change or delete your links.

You can have **several keys**, one for each thing that saves links: the iPhone Shortcut, the browser extension on each computer, a script. They all work the same way, at the same address. The difference is that each one can be removed on its own: when you lose your phone, remove its key and the extension keeps working.

1. In **👤 Your account → Save from anywhere**, press **Create API key**.
2. Give it a **name** that says where it will be used, for example *iPhone Shortcut* or *Edge on the laptop*.
3. **Copy it now**: it is shown only once. Paste it into the Shortcut, the extension or the script.

The list under **API keys** shows each key with its name, the first characters of the key, when it was **last used** and when it was made.

- **Rename** changes only the name; the key itself stays the same.
- **Remove** switches that one key off. Whatever uses it gets *not valid*; your other keys keep working.
- **Lost a key?** It can't be shown again. Create a new one, paste it where the old one was, and remove the old one.

An account can have up to 20 keys. Keys belong to their account: links sent with a key go to that account, nobody else sees your keys (an admin neither), and removing an account removes its keys. Keys are not in your own backup; a backup of the whole installation brings them back with the accounts.

> **Upgrading from 2.10 or earlier:** the one key you had becomes the first key in the list, named **Default**. It keeps working, so nothing needs to change in your Shortcut or extension. Its first characters aren't known, so the list shows *made before 2.11* instead. Rename it to where you use it, or give each device its own key and remove **Default** once nothing uses it any more.

The [browser extension](browser-extension.md) uses an API key too: make it its own.

### Adding a link

Send a `POST` to `/api/links` with the key in the `Authorization` header:

```bash
curl -X POST https://tilemark.example.com/api/links \
  -H "Authorization: Bearer tm_your_key" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com/article", "group": "Reading", "note": "read later"}'
```

| Field | Required | Meaning |
| --- | --- | --- |
| `url` | yes | The address to save. |
| `group` | no | Group **name**. Created if it doesn't exist yet. |
| `group_id` | no | Group **number**, instead of the name. |
| `title` | no | Your own title. Without it, the page's title is used. |
| `note` | no | A note for the card. |

### Listing your groups

```bash
curl https://tilemark.example.com/api/groups -H "Authorization: Bearer tm_your_key"
```

returns your groups with their names and numbers.

### iPhone Shortcut

1. In the **Shortcuts** app, create a shortcut and turn on **Show in Share Sheet**, receiving **URLs**.
2. Add the action **Get Contents of URL**:
   - URL: `https://<your-tilemark>/api/links`
   - Method: **POST**
   - Headers: `Authorization` = `Bearer tm_your_key`
   - Request body: **JSON**, with `url` = *Shortcut Input* and, if you like, `group` = `Phone`.
3. Name it "Save to TileMark".

Now **Share → Save to TileMark** works from Safari and most apps.

### From Home Assistant

A `rest_command` can save links from an automation or a script:

```yaml
rest_command:
  tilemark_save:
    url: "http://<your-tilemark>:8080/api/links"
    method: POST
    headers:
      Authorization: "Bearer tm_your_key"
    content_type: "application/json"
    payload: '{"url": "{{ url }}", "group": "{{ group | default(''Inbox'') }}"}'
```
