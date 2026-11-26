// Background: the right-click menu ("Save page / Save link to TileMark") and the first
// start. The toolbar window (popup.html) does its own saving.
import { saveLink } from "./lib/api.js";
import { errorText, loadLanguage, t } from "./lib/i18n.js";
import { getSettings } from "./lib/settings.js";

async function buildMenus() {
  if (!chrome.contextMenus) return;  // Firefox for Android has no right-click menu
  const settings = await getSettings();
  await loadLanguage(settings.language);
  await chrome.contextMenus.removeAll();
  chrome.contextMenus.create({ id: "save-page", title: t("menuSavePage"), contexts: ["page"] });
  chrome.contextMenus.create({ id: "save-link", title: t("menuSaveLink"), contexts: ["link"] });
}

chrome.runtime.onInstalled.addListener(async ({ reason }) => {
  await buildMenus();
  if (reason === "install") chrome.runtime.openOptionsPage();
});

chrome.runtime.onStartup.addListener(buildMenus);

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "local" && "language" in changes) buildMenus();
});

// A short mark on the toolbar icon of that tab: ✓ saved, = already there, ! something wrong
// (hover the icon to read what).
function badge(tabId, text, color, title) {
  if (tabId === undefined || tabId < 0) return;
  chrome.action.setBadgeBackgroundColor({ tabId, color });
  chrome.action.setBadgeText({ tabId, text });
  chrome.action.setTitle({ tabId, title });
  setTimeout(() => {
    chrome.action.setBadgeText({ tabId, text: "" });
    chrome.action.setTitle({ tabId, title: t("actionTitle") });
  }, 6000);
}

chrome.contextMenus?.onClicked.addListener(async (info, tab) => {
  const settings = await getSettings();
  await loadLanguage(settings.language);
  if (!settings.server || !settings.apiKey) {
    chrome.runtime.openOptionsPage();
    return;
  }
  const isLink = info.menuItemId === "save-link";
  const url = isLink ? info.linkUrl : info.pageUrl || tab?.url;
  if (!url || !/^https?:/i.test(url)) {
    badge(tab?.id, "!", "#d6453d", t("cannotSave"));
    return;
  }
  const link = { url };
  if (!isLink && tab?.title) link.title = tab.title;
  const group = settings.menuGroup === "last" ? settings.lastGroup : settings.menuGroup;
  if (group) link.group_id = Number(group);
  try {
    await saveLink(settings, link);
    badge(tab?.id, "✓", "#2f9e5b", t("saved"));
  } catch (err) {
    if (err.kind === "duplicate") {
      const e = err.existing || {};
      const title = e.group ? t("alreadyIn", { group: e.group, title: e.title || e.url }) : t("already", { title: e.title || e.url });
      badge(tab?.id, "=", "#2f6fe4", title);
    } else {
      badge(tab?.id, "!", "#d6453d", errorText(err, settings.server));
    }
  }
});
