// Languages. The texts live in _locales/<code>/messages.json (the browser's own format, so
// the store listing and the menus use them too). They are read here directly, so the
// language can also be chosen in the settings instead of always following the browser.
// "{name}" in a text is filled in by t(key, { name }).

// Same order and names as TileMark itself.
export const LANGUAGES = [
  { code: "en", name: "English" },
  { code: "nl", name: "Nederlands" },
  { code: "de", name: "Deutsch" },
  { code: "fr", name: "Français" },
  { code: "es", name: "Español" },
  { code: "ar", name: "العربية", dir: "rtl" }
];

let current = "en";
let messages = {};
let fallback = {};

async function read(code) {
  const r = await fetch(chrome.runtime.getURL(`_locales/${code}/messages.json`));
  return r.json();
}

export async function loadLanguage(setting) {
  const codes = LANGUAGES.map((l) => l.code);
  const browser = (chrome.i18n.getUILanguage() || "en").toLowerCase().split("-")[0];
  current = setting && setting !== "auto" && codes.includes(setting) ? setting : codes.includes(browser) ? browser : "en";
  fallback = await read("en");
  messages = current === "en" ? fallback : await read(current);
  return current;
}

export function t(key, vars = {}) {
  const text = (messages[key] || fallback[key] || { message: key }).message;
  return text.replace(/\{(\w+)\}/g, (_, name) => (vars[name] ?? "").toString());
}

export function direction() {
  return LANGUAGES.find((l) => l.code === current)?.dir || "ltr";
}

// data-i18n="key" sets the text, data-i18n-placeholder / data-i18n-title / data-i18n-aria
// set those attributes.
export function translatePage(root = document) {
  document.documentElement.lang = current;
  document.documentElement.dir = direction();
  for (const el of root.querySelectorAll("[data-i18n]")) el.textContent = t(el.dataset.i18n);
  for (const el of root.querySelectorAll("[data-i18n-placeholder]")) el.placeholder = t(el.dataset.i18nPlaceholder);
  for (const el of root.querySelectorAll("[data-i18n-title]")) el.title = t(el.dataset.i18nTitle);
  for (const el of root.querySelectorAll("[data-i18n-aria]")) el.setAttribute("aria-label", t(el.dataset.i18nAria));
}

// An ApiError as a sentence for the person.
export function errorText(err, server = "") {
  const host = server ? server.replace(/^https?:\/\//, "") : "";
  if (err && err.kind === "server") return t("err_server", { message: err.message });
  if (err && err.kind) return t(`err_${err.kind}`, { server: host });
  return t("err_server", { message: String(err) });
}
