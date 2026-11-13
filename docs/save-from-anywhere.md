# Save from anywhere

You don't have to open TileMark to save a link. There are three ways to send a page to it from wherever you are.

| Way | Best for | Needs |
| --- | --- | --- |
| [Browser button](#browser-button) | Your computer | Being signed in to TileMark in that browser |
| [Phone app](#phone) | Android, from any app's Share menu | TileMark on an HTTPS address |
| [API key](#api-key) | Scripts, iPhone Shortcuts, automations | An API key from Settings |

All three are found in **⚙ Settings → Save from anywhere**.

> **Home Assistant add-on:** these need TileMark's own address, not the sidebar. See [TileMark's own address](home-assistant-add-on.md#tilemarks-own-address-optional).

## Browser button

1. Open **⚙ Settings → Save from anywhere**.
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

1. In **⚙ Settings → Save from anywhere**, press **Create API key**.
2. **Copy it now**: it is shown only once. If you lose it, press **Replace API key** for a new one (the old one stops working).
3. **Remove API key** switches it off.

Every account has its own key, and links sent with it go to that account.

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
