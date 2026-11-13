// TileMark keeps nothing offline; this file only exists so the app can be installed.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil(self.clients.claim()));
