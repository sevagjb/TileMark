// The toolbar window: the current page, a group, a note, Save.
import { listGroups, saveLink } from "./lib/api.js";
import { errorText, loadLanguage, t, translatePage } from "./lib/i18n.js";
import { getSettings, setSettings } from "./lib/settings.js";

const $ = (id) => document.getElementById(id);
const NEW = "__new__";
let settings;
let page = { url: "", title: "" };
let groups = [];

function show(id) {
  for (const s of ["setup", "cannot", "form", "result"]) $(s).hidden = s !== id;
}

function showError(err) {
  $("error").textContent = typeof err === "string" ? err : errorText(err, settings.server);
  $("error").hidden = false;
}

function fillGroups(selected) {
  const sel = $("group");
  sel.replaceChildren();
  sel.add(new Option(t("noGroup"), ""));
  for (const g of groups) sel.add(new Option(g.name, String(g.id)));
  sel.add(new Option(t("newGroup"), NEW));
  sel.value = groups.some((g) => String(g.id) === String(selected)) ? String(selected) : "";
}

async function init() {
  settings = await getSettings();
  await loadLanguage(settings.language);
  translatePage();
  $("settings").onclick = $("openSettings").onclick = () => {
    chrome.runtime.openOptionsPage();
    window.close();
  };
  $("openTileMark").onclick = () => {
    chrome.tabs.create({ url: settings.server + "/" });
    window.close();
  };

  if (!settings.server || !settings.apiKey) return show("setup");

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !/^https?:/i.test(tab.url || "")) return show("cannot");
  page = { url: tab.url, title: tab.title || "" };
  $("title").value = page.title;
  $("url").textContent = page.url;
  $("url").title = page.url;

  show("form");
  const sel = $("group");
  sel.add(new Option(t("loadingGroups"), ""));
  sel.disabled = true;
  $("note").focus();
  try {
    groups = await listGroups(settings);
    fillGroups(settings.lastGroup);
  } catch (err) {
    fillGroups("");
    showError(err);
    if (["badKey", "offline", "noPermission", "redirect", "notTileMark", "refused"].includes(err.kind)) {
      $("save").disabled = true;
    }
  } finally {
    sel.disabled = false;
  }
}

$("group").addEventListener("change", () => {
  const isNew = $("group").value === NEW;
  $("newGroup").hidden = !isNew;
  if (isNew) $("newGroup").focus();
});

// Ctrl+Enter (Cmd+Enter on a Mac) in the note saves; Enter alone makes a new line.
$("note").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) $("form").requestSubmit();
});

function linkFromForm(allowDuplicate = false) {
  const link = { url: page.url };
  const title = $("title").value.trim();
  const note = $("note").value.trim();
  if (title) link.title = title;
  if (note) link.note = note;
  const g = $("group").value;
  if (g === NEW) {
    const name = $("newGroup").value.trim();
    if (name) link.group = name;
  } else if (g) {
    link.group_id = Number(g);
  }
  if (allowDuplicate) link.allow_duplicate = true;
  return link;
}

function groupName(link) {
  if (link.group) return link.group;
  return groups.find((g) => g.id === link.group_id)?.name || "";
}

async function rememberGroup(link) {
  if (link.group_id) return setSettings({ lastGroup: String(link.group_id) });
  if (!link.group) return setSettings({ lastGroup: "" });
  try { // a new group: look up the number TileMark gave it
    const made = (await listGroups(settings)).find((g) => g.name.toLowerCase() === link.group.toLowerCase());
    return setSettings({ lastGroup: made ? String(made.id) : "" });
  } catch {
    return undefined;
  }
}

async function submit(allowDuplicate) {
  $("error").hidden = true;
  const link = linkFromForm(allowDuplicate);
  if ($("group").value === NEW && !link.group) {
    $("newGroup").focus();
    return;
  }
  $("save").disabled = true;
  $("save").textContent = t("saving");
  $("saveAnyway").disabled = true;
  try {
    await saveLink(settings, link);
    await rememberGroup(link);
    const name = groupName(link);
    $("resultText").textContent = name ? t("savedTo", { group: name }) : t("saved");
    $("resultText").className = "message good";
    $("saveAnyway").hidden = true;
    show("result");
    setTimeout(() => window.close(), 1600);
  } catch (err) {
    if (err.kind === "duplicate") {
      const e = err.existing || {};
      const title = e.title || e.url;
      $("resultText").textContent = e.group ? t("alreadyIn", { group: e.group, title }) : t("already", { title });
      $("resultText").className = "message";
      // TileMark never stores the very same address twice; a page that only looks the same
      // (another tracking code, http vs https) may be saved anyway.
      $("saveAnyway").hidden = allowDuplicate || e.url === page.url;
      $("saveAnyway").disabled = false;
      show("result");
    } else {
      showError(err);
    }
  } finally {
    $("save").disabled = false;
    $("save").textContent = t("save");
  }
}

$("form").addEventListener("submit", (e) => {
  e.preventDefault();
  submit(false);
});
$("saveAnyway").addEventListener("click", () => submit(true));

init();
