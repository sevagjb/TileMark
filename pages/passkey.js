// Passkeys in the browser, for the sign-in page and Settings. The server sends its options
// as JSON (binary parts as base64url); navigator.credentials wants them as bytes, and its
// answer goes back as JSON again. Written out by hand so it also works in browsers without
// PublicKeyCredential.parseCreationOptionsFromJSON / toJSON.
(function () {
"use strict";
const dec = s => Uint8Array.from(atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), c => c.charCodeAt(0)).buffer;
const enc = buf => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");

// Browsers offer passkeys only on HTTPS (or http://localhost) and never on an IP address.
function canUse() {
  const h = location.hostname;
  return !!(window.PublicKeyCredential && navigator.credentials && window.isSecureContext)
    && !/^\d{1,3}(\.\d{1,3}){3}$/.test(h) && !h.includes(":") && !h.startsWith("[");
}

async function create(o) {
  o.challenge = dec(o.challenge);
  o.user.id = dec(o.user.id);
  (o.excludeCredentials || []).forEach(c => { c.id = dec(c.id); });
  const c = await navigator.credentials.create({ publicKey: o });
  return {
    id: c.id, rawId: enc(c.rawId), type: c.type, authenticatorAttachment: c.authenticatorAttachment || undefined,
    clientExtensionResults: c.getClientExtensionResults ? c.getClientExtensionResults() : {},
    response: {
      clientDataJSON: enc(c.response.clientDataJSON), attestationObject: enc(c.response.attestationObject),
      transports: c.response.getTransports ? c.response.getTransports() : []
    }
  };
}

async function get(o) {
  o.challenge = dec(o.challenge);
  (o.allowCredentials || []).forEach(c => { c.id = dec(c.id); });
  const c = await navigator.credentials.get({ publicKey: o });
  return {
    id: c.id, rawId: enc(c.rawId), type: c.type, authenticatorAttachment: c.authenticatorAttachment || undefined,
    clientExtensionResults: c.getClientExtensionResults ? c.getClientExtensionResults() : {},
    response: {
      clientDataJSON: enc(c.response.clientDataJSON), authenticatorData: enc(c.response.authenticatorData),
      signature: enc(c.response.signature), userHandle: c.response.userHandle ? enc(c.response.userHandle) : null
    }
  };
}

// The browser's own errors, in words a person understands (translated by t() where loaded).
function message(e, t) {
  t = t || (s => s);
  if (e && e.name === "NotAllowedError") return t("No passkey was used. It was cancelled, or it took too long.");
  if (e && e.name === "InvalidStateError") return t("This device already has a passkey for your account.");
  if (e && e.name === "SecurityError") return t("Passkeys only work on TileMark's HTTPS address with a name, not on an IP address or plain http.");
  return (e && e.message) || t("Something went wrong.");
}

self.TMPasskey = { canUse, create, get, message };
})();
