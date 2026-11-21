// The two things an API key may do on TileMark: read the group names and add a link.
// Every call goes with the key in the Authorization header and without cookies, so the
// extension never acts as the signed-in browser.
import { originPattern } from "./settings.js";

export class ApiError extends Error {
  // kind: setup | noPermission | offline | redirect | notTileMark | badKey | refused | duplicate | server
  constructor(kind, message = "", existing = null) {
    super(message || kind);
    this.kind = kind;
    this.existing = existing;
  }
}

async function call(settings, method, path, body) {
  if (!settings.server || !settings.apiKey) throw new ApiError("setup");
  if (!(await chrome.permissions.contains({ origins: [originPattern(settings.server)] }))) {
    throw new ApiError("noPermission");
  }
  let r;
  try {
    r = await fetch(settings.server + path, {
      method,
      headers: {
        Authorization: `Bearer ${settings.apiKey}`,
        Accept: "application/json",
        ...(body ? { "Content-Type": "application/json" } : {})
      },
      body: body ? JSON.stringify(body) : undefined,
      credentials: "omit",
      cache: "no-store",
      redirect: "manual" // a login page in front of TileMark shows up as a redirect
    });
  } catch {
    throw new ApiError("offline");
  }
  if (r.type === "opaqueredirect" || (r.status >= 300 && r.status < 400)) throw new ApiError("redirect");
  let data = null;
  try {
    data = await r.json();
  } catch {
    data = null;
  }
  if (r.ok) {
    if (!data || typeof data !== "object") throw new ApiError("notTileMark");
    return data;
  }
  if (r.status === 401) throw new ApiError("badKey");
  if (r.status === 403) throw new ApiError("refused"); // a proxy rule in front, or an older TileMark
  if (r.status === 409 && data && data.existing) throw new ApiError("duplicate", data.error, data.existing);
  if (r.status === 404 || !data) throw new ApiError("notTileMark");
  throw new ApiError("server", data.error || `HTTP ${r.status}`);
}

export async function listGroups(settings) {
  const data = await call(settings, "GET", "/api/groups");
  if (!Array.isArray(data.groups)) throw new ApiError("notTileMark");
  return data.groups;
}

// link: { url, title?, note?, group_id? | group?, allow_duplicate? } → { id }
export function saveLink(settings, link) {
  return call(settings, "POST", "/api/links", link);
}
