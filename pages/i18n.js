// TileMark interface languages.
// English is the base language: the English text in the pages is the key, and any text a
// language file doesn't translate (missing or empty) is shown in English.
// The translations live in pages/lang/<code>.json, one file per language, and the list of
// languages in pages/lang/languages.json. The server puts the chosen language in front of
// this script as TM_I18N_DATA, so only that language is sent and nothing waits to load.
// How to add a language: docs/translating.md.
(function () {
"use strict";
const data = self.TM_I18N_DATA || {};
const LIST = data.languages || [{ code: "en", name: "English" }];
const INFO = LIST.find(l => l.code === data.lang) || LIST[0];
const lang = INFO.code;
const D = data.dict || {};
const plural = (() => { try { return new Intl.PluralRules(INFO.locale || lang); } catch (e) { return null; } })();

// Server messages with a variable part: the regex finds the parts, the English template is
// the key in the language files.
const PATTERNS = [
  [/^This page is already saved in "(.+)": (.+)$/, 'This page is already saved in "{group}": {title}', ["group", "title"]],
  [/^This page is already saved: (.+)$/, "This page is already saved: {title}", ["title"]],
  [/^Too many attempts\. Try again in (\d+) seconds\.$/, "Too many attempts. Try again in {n} seconds.", ["n"]],
  [/^This file is too large \(at most (\d+) MB\)\.$/, "This file is too large (at most {n} MB).", ["n"]],
  [/^To confirm, type the date of the backup: (.+)$/, "To confirm, type the date of the backup: {date}", ["date"]],
  [/^Broker refused the connection: (.+)$/, "Broker refused the connection: {error}", ["error"]],
  [/^Connection lost \((.+)\); retrying\.$/, "Connection lost ({error}); retrying.", ["error"]]
];

// A translation is a text, or for texts with a count an object with the language's plural
// forms (zero, one, two, few, many, other), chosen by the number in {n}.
function lookup(key, v) {
  const e = D[key];
  if (typeof e === "string") return e;
  if (e && typeof e === "object") {
    const n = v && v.n !== undefined && v.n !== "" ? Number(v.n) : NaN;
    return (plural && !isNaN(n) && e[plural.select(n)]) || e.other || "";
  }
  return "";
}
function fill(s, v) {
  return v ? s.replace(/\{(\w+)\}/g, (m, k) => (k in v ? String(v[k]) : m)) : s;
}
function t(s, v) {
  s = s == null ? "" : String(s);
  if (lang === "en") return fill(s, v);
  let out = lookup(s, v);
  if (!out) {
    for (const [re, key, names] of PATTERNS) {
      const m = s.match(re);
      if (!m) continue;
      const vars = Object.assign({}, v);
      names.forEach((nm, i) => { vars[nm] = m[i + 1]; });
      const tr = lookup(key, vars);
      if (tr) return fill(tr, vars);
      break;
    }
    out = s;  // not translated: show the English
  }
  return fill(out, v);
}

const ATTRS = ["placeholder", "title", "aria-label"];
function applyI18n(root) {
  if (lang === "en" || !root) return;
  const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode: n => (n.parentNode && /^(SCRIPT|STYLE|svg|CODE)$/i.test(n.parentNode.nodeName)) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT
  });
  const nodes = [];
  while (w.nextNode()) nodes.push(w.currentNode);
  for (const n of nodes) {
    const raw = n.nodeValue, k = raw.trim(), v = k && lookup(k);
    if (v) n.nodeValue = raw.replace(k, v);
  }
  for (const el of (root.querySelectorAll ? root.querySelectorAll("[placeholder],[title],[aria-label]") : []))
    for (const a of ATTRS) { const v = lookup((el.getAttribute(a) || "").trim()); if (v) el.setAttribute(a, v); }
  const title = lookup(document.title);
  if (title) document.title = title;
}

// The chosen language ("" = follow the browser). The server remembers it in a cookie for the
// sign-in page; once signed in, the account's choice decides.
const COOKIE = "tm_lang";
function setLang(l) {
  try { document.cookie = COOKIE + "=" + encodeURIComponent(l || "") + ";max-age=" + (l ? 31536000 : 0) + ";samesite=lax"; } catch (e) {}
  try { localStorage.removeItem("tm.lang"); } catch (e) {}  // where 2.5 and earlier kept it
}
const pref = data.pref || "";
(function keepInStep() {
  let cookie = null;
  try { const m = document.cookie.match(/(?:^|;\s*)tm_lang=([^;]*)/); cookie = m ? decodeURIComponent(m[1]) : null; } catch (e) { return; }
  if (data.from === "account") { if ((cookie || "") !== pref) setLang(pref); return; }
  // Upgrading from 2.5 or earlier: the choice was kept in this browser's storage. Move it to
  // the cookie and reload once to show it (only if the cookie took, so this can't loop).
  let old = "";
  try { old = localStorage.getItem("tm.lang") || ""; } catch (e) {}
  if (cookie === null && old && old !== lang && LIST.some(l => l.code === old)) {
    setLang(old);
    if (document.cookie.indexOf(COOKIE + "=") >= 0) location.reload();
  }
})();

window.t = t;
window.applyI18n = applyI18n;
window.tmLang = () => lang;
window.TM_LANGS = Object.fromEntries(LIST.map(l => [l.code, l.name]));
window.TM_LANG_LIST = LIST;
window.setLang = setLang;
window.storedLang = () => pref;
window.fmtDate = (ts, time) => {
  const d = new Date(ts * 1000), loc = INFO.locale || undefined;
  return time ? d.toLocaleString(loc) : d.toLocaleDateString(loc);
};
document.documentElement.lang = lang;
document.documentElement.dir = INFO.dir === "rtl" ? "rtl" : "ltr";
if (document.body) applyI18n(document.body);
else document.addEventListener("DOMContentLoaded", () => applyI18n(document.body));
})();
