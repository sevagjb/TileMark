// Settings: TileMark's address and the API key, the right-click group and the language.
import { listGroups } from "./lib/api.js";
import { LANGUAGES, errorText, loadLanguage, t, translatePage } from "./lib/i18n.js";
import { clearSettings, getSettings, normalizeServer, originPattern, setSettings } from "./lib/settings.js";

const $ = (id) => document.getElementById(id);
let settings;
let groups = [];

function status(text, kind = "") {
  $("status").textContent = text;
  $("status").className = kind;
}

// Two things worth saying before anything is saved: plain http, and Home Assistant's
// own address (the sidebar needs a Home Assistant sign-in the extension doesn't have).
function warnAbout(server) {
  const notes = [];
  if (server.startsWith("http://")) notes.push(t("warnHttp"));
  if (/\/api\/hassio_ingress\//.test(server) || /:8123$/.test(new URL(server).host)) notes.push(t("warnHomeAssistant"));
  $("serverWarn").textContent = notes.join(" ");
  $("serverWarn").hidden = !notes.length;
}

function fillMenuGroups() {
  const sel = $("menuGroup");
  sel.replaceChildren(new Option(t("menuGroupLast"), "last"), new Option(t("noGroup"), ""));
  for (const g of groups) sel.add(new Option(g.name, String(g.id)));
  const known = ["last", ""].includes(settings.menuGroup) || groups.some((g) => String(g.id) === settings.menuGroup);
  sel.value = known ? settings.menuGroup : "last";
}

function fillLanguages() {
  const sel = $("language");
  sel.replaceChildren(new Option(t("languageAuto"), "auto"));
  for (const l of LANGUAGES) sel.add(new Option(l.name, l.code));
  sel.value = settings.language;
}

// The shortcut the browser really uses for the Save window: the default differs per browser
// (Alt+Shift+S in Edge and Chrome, Ctrl+Shift+L in Firefox, where Alt+S opens the History
// menu), and people can change it. Key names in the chosen language ("Umschalt", "Maj"…).
async function showShortcut() {
  let keys = "";
  try {
    const commands = await chrome.commands.getAll();
    keys = commands.find((c) => c.name === "_execute_action")?.shortcut || "";
  } catch { /* no commands API: say nothing is set */ }
  const names = { Shift: t("keyShift"), Ctrl: t("keyCtrl") };
  keys = keys.split("+").map((k) => names[k] || k).join("+");
  $("shortcutText").textContent = keys ? t("shortcutHint", { keys }) : t("shortcutNone");
}

async function render() {
  await loadLanguage(settings.language);
  translatePage();
  fillMenuGroups();
  fillLanguages();
  await showShortcut();
  $("showKey").textContent = $("apiKey").type === "password" ? t("show") : t("hide");
}

async function test() {
  status(t("testing"));
  try {
    groups = await listGroups(settings);
    fillMenuGroups();
    status(t("connected", { count: groups.length }), "good");
  } catch (err) {
    status(errorText(err, settings.server), "error");
  }
}

$("form").addEventListener("submit", (e) => {
  e.preventDefault();
  const server = normalizeServer($("server").value);
  const apiKey = $("apiKey").value.trim();
  if (!server) return status(t("invalidAddress"), "error");
  if (!apiKey) return status(t("err_badKey"), "error");
  $("server").value = server;
  warnAbout(server);
  const wanted = originPattern(server);
  const before = settings.server ? originPattern(settings.server) : "";
  // Asked straight from the click: browsers only show this question in answer to one.
  chrome.permissions.request({ origins: [wanted] }).then(async (granted) => {
    if (!granted) return status(t("permissionDenied", { server: server.replace(/^https?:\/\//, "") }), "error");
    if (before && before !== wanted) await chrome.permissions.remove({ origins: [before] }).catch(() => {});
    settings = { ...settings, server, apiKey };
    await setSettings({ server, apiKey });
    await test();
  }).catch((err) => status(t("err_server", { message: err.message || String(err) }), "error"));
});

$("server").addEventListener("change", () => {
  const server = normalizeServer($("server").value);
  if (server) warnAbout(server);
});

$("showKey").addEventListener("click", () => {
  const hidden = $("apiKey").type === "password";
  $("apiKey").type = hidden ? "text" : "password";
  $("showKey").textContent = hidden ? t("hide") : t("show");
});

$("menuGroup").addEventListener("change", async () => {
  settings.menuGroup = $("menuGroup").value;
  await setSettings({ menuGroup: settings.menuGroup });
});

$("language").addEventListener("change", async () => {
  settings.language = $("language").value;
  await setSettings({ language: settings.language });
  await render();
  if ($("status").textContent && settings.server) await test();
});

$("shortcuts").addEventListener("click", (e) => {
  e.preventDefault();
  // Firefox has no shortcuts page to link to, but opens its own setting (about:addons) for us
  if (chrome.commands?.openShortcutSettings) return void chrome.commands.openShortcutSettings();
  const edge = navigator.userAgent.includes("Edg/");
  chrome.tabs.create({ url: edge ? "edge://extensions/shortcuts" : "chrome://extensions/shortcuts" });
});

$("forget").addEventListener("click", async () => {
  if (settings.server) await chrome.permissions.remove({ origins: [originPattern(settings.server)] }).catch(() => {});
  await clearSettings();
  settings = await getSettings();
  groups = [];
  $("server").value = "";
  $("apiKey").value = "";
  $("serverWarn").hidden = true;
  status("");
  await render();
  $("forgotten").textContent = t("forgotten");
});

async function init() {
  settings = await getSettings();
  $("server").value = settings.server;
  $("apiKey").value = settings.apiKey;
  $("version").textContent = "v" + chrome.runtime.getManifest().version;
  await render();
  if (settings.server) {
    warnAbout(settings.server);
    if (settings.apiKey) await test();
  }
}

init();
