# Roadmap

Status of planned work. Numbers match the list agreed for the next rounds.

## Done

- [x] **1. Backup and restore**, with optional password encryption (Settings → Backup / Restore).

## 2. Ready-made Docker image (in progress)

Goal: anyone can install LinkBoard with a one-line `image:` in their compose, and updates are a pull instead of a build.

What exists:

- `.github/workflows/docker.yml` builds on every push to `main` and on `v*` tags, for `linux/amd64` and `linux/arm64`, and pushes to `ghcr.io/sevagjb/linkboard`.
- The workflow has been running successfully since 2026-11-11 22:23 UTC (the very first run stayed queued and can be cancelled).

What is left:

1. **Make the package public.** GitHub → profile → Packages → `linkboard` → Package settings → Change visibility → Public. Until then pulls are denied.
2. **Verify an anonymous pull** from a machine that is not logged in to ghcr.io: `docker pull ghcr.io/sevagjb/linkboard:latest`.
3. **Switch the own installation** from build-from-source to the image (compose below) and confirm Update in Dockge pulls a new version.
4. **First release tag** `v1.0.0`, so people can pin a version (`ghcr.io/sevagjb/linkboard:1.0.0`) instead of `latest`.
5. **README for others:** screenshot, short "what is it", install in three steps, update instructions, link to this roadmap.
6. Optional: add a changelog. (The image is already labelled with its source repository, so GitHub links the package to the repo.)

Compose to use once the package is public:

```yaml
services:
  linkboard:
    image: ghcr.io/sevagjb/linkboard:latest
    container_name: linkboard
    restart: unless-stopped
    # environment:
    #   - BEHIND_PROXY=1   # only when running behind a reverse proxy
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
```

## Next rounds

Saving links faster
- [ ] **3.** "Save to LinkBoard" browser button (bookmarklet) with group picker; needs an API key in Settings.
- [ ] **4.** Install as an app on the phone and appear in the Share menu (needs HTTPS).

Finding and keeping order
- [ ] **5.** Pin favourites to the top of a group / a Favourites entry.
- [ ] **6.** Notes and tags on a link.
- [ ] **7.** Sort options per group: own order, newest, name, site.
- [ ] **8.** Recently added and recently opened.

Keeping the collection healthy
- [ ] **9.** Dead-link check that marks links that no longer work.
- [ ] **10.** Own picture for a card (upload or paste).
- [ ] **11.** Refresh all thumbnails of a group.

## Later

- [ ] **12.** Keep a readable copy of the page.
- [ ] **13.** Several users, each with their own links.
- [ ] **14.** Interface in other languages.
- [ ] Nightly automatic backup kept in the data folder.
- [ ] Option to require creating a login on first start.
