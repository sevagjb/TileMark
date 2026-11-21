// What the extension keeps. storage.local stays in this browser: it is never copied to
// other devices by browser sync, so the API key only lives where it was pasted.
export const DEFAULTS = {
  server: "",      // TileMark's address, e.g. "https://tilemark.example.com" (no trailing slash)
  apiKey: "",      // "tm_…", from TileMark: Your account → Save from anywhere
  language: "auto",
  lastGroup: "",   // group id last picked in the Save window ("" = no group)
  menuGroup: "last" // where right-click saves: "last", "" (no group) or a group id
};

export async function getSettings() {
  return { ...DEFAULTS, ...(await chrome.storage.local.get(Object.keys(DEFAULTS))) };
}

export function setSettings(values) {
  return chrome.storage.local.set(values);
}

export function clearSettings() {
  return chrome.storage.local.clear();
}

// Addresses on the home network, which almost always run plain http: an IP address,
// localhost, or a name ending in .local, .lan, .home or .internal.
const LOCAL = /^(\d{1,3}(\.\d{1,3}){3}|\[[0-9a-f:]+\]|localhost|[^/]+\.(local|lan|home|internal))(:\d+)?([/?#]|$)/i;

// "tilemark.example.com/" → "https://tilemark.example.com", "192.168.1.5:8080" →
// "http://192.168.1.5:8080". Keeps a path (TileMark can sit under one behind a proxy),
// drops query and fragment. "" when it isn't a web address.
export function normalizeServer(text) {
  let s = String(text || "").trim();
  if (!s) return "";
  if (!/^[a-z][a-z0-9+.-]*:\/\//i.test(s)) s = (LOCAL.test(s) ? "http://" : "https://") + s;
  let u;
  try {
    u = new URL(s);
  } catch {
    return "";
  }
  if (!["http:", "https:"].includes(u.protocol) || !u.hostname) return "";
  return (u.origin + u.pathname).replace(/\/+$/, "");
}

// The one site the extension asks to reach. A match pattern without a port covers every
// port on that host, so "http://192.168.1.5:8080" works too.
export function originPattern(server) {
  const u = new URL(server);
  return `${u.protocol}//${u.hostname}/*`;
}
