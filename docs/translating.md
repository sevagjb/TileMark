# Translating TileMark

TileMark's interface is in **English, Nederlands, Deutsch and العربية**. Adding a language takes one file and one line, with no code changes. A language can also be released half-finished: anything not translated yet is shown in English.

## How the languages are organised

```
pages/lang/languages.json   the list of languages, in the order of the Language menu
pages/lang/nl.json          Dutch
pages/lang/de.json          German
pages/lang/ar.json          Arabic
```

- **English is the base language.** The English text in the app is the key, so there is no `en.json`.
- **Each language file** pairs every English text with its translation:

  ```json
  "Guide and help": "Anleitung und Hilfe",
  "Delete this link?": "Diesen Link löschen?",
  ```

- **An empty translation (`""`)** means "not translated yet", and that text is shown in English.
- **`languages.json`** decides which languages exist and their order in **⚙ Settings → Appearance → Language**:

  ```json
  { "code": "ar", "name": "العربية", "locale": "ar-u-nu-latn", "dir": "rtl" }
  ```

  | Field | Meaning |
  |---|---|
  | `code` | The language code (`fr`, `es`, `pt-BR` …). The file is `<code>.json`. |
  | `name` | The name shown in the menu, written in the language itself. |
  | `locale` | Optional: how dates are written (`fr-FR`). Leave it out to use the browser's format. |
  | `dir` | `"rtl"` for languages written right to left. The whole page is then mirrored. |

TileMark sends only the chosen language to the browser, so more languages don't make the app heavier.

## Add a language

1. Start the file. From the repository folder:

   ```
   python3 scripts/i18n_check.py --new fr Français --locale fr-FR
   ```

   This creates `pages/lang/fr.json` with every text and an empty translation, and adds Français to the end of `languages.json`. For a right-to-left language, add `--rtl`.
2. Translate the texts in `fr.json`. You can do this in steps: empty ones stay English.
3. Restart TileMark (or rebuild the image) and choose the language in **⚙ Settings → Appearance → Language**.
4. See how far it is:

   ```
   python3 scripts/i18n_check.py
   ```

   It shows how much of each language is translated, any texts missing from a file, and texts that nothing seems to use any more.
5. Run the tests (`python3 -m pytest`) and open a pull request.

To change the order in the menu, move the lines in `languages.json`.

## Rules for translations

- **Keep the `{placeholders}` exactly as they are.** `{n}`, `{name}`, `{when}` … are filled in by TileMark. The tests fail if one is missing, misspelled or added.
- **Keep line breaks (`\n`)** where the English has them; they separate the question from the explanation in confirmation boxes.
- **Use the informal "you"** (du, je, tu), like the existing languages.
- **Don't translate** TileMark, Home Assistant, MQTT, API, TLS, 2FA, Dockge or the names of buttons in other apps.

## Plural forms

Most texts with a count come in two keys, chosen by TileMark: `"{n} link"` for 1 and `"{n} links"` for any other number. That is enough for languages like Dutch, German, French or Spanish.

Languages with more forms can give an object instead of a text. The browser picks the right form for the number in `{n}`:

```json
"{n} links": {
  "zero": "{n} روابط",
  "one": "رابط واحد",
  "two": "رابطان",
  "few": "{n} روابط",
  "many": "{n} رابطًا",
  "other": "{n} رابط"
}
```

- The forms are `zero`, `one`, `two`, `few`, `many` and `other`, as defined by Unicode for each language. Only `other` is required; a missing form falls back to `other`.
- `zero`, `one` and `two` may leave out `{n}` ("رابط واحد"); the other forms must keep it.
- Give the same object for both keys (`"{n} link"` and `"{n} links"`), because TileMark may ask for either one.
- Arabic uses all six forms; Polish, Russian and Czech use `one`, `few`, `many` and `other`.
