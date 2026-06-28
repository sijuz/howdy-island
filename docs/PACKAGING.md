# Packaging & distribution

This document explains how to publish `howdy-island` so users can install it
**through their package manager** instead of downloading a file by hand.

Two channels are set up here:

| Channel | Builds for | Source files |
| ------- | ---------- | ------------ |
| **Fedora COPR** | Fedora / RHEL / openSUSE (RPM) | [`packaging/howdy-island.spec`](../packaging/howdy-island.spec) |
| **openSUSE Build Service (OBS)** | Debian / Ubuntu (DEB) **and** RPM distros | [`packaging/obs/`](../packaging/obs) + the spec |

> The application is pure-Python and architecture-independent (`noarch` /
> `Architecture: all`). All packages install the same layout:
>
> - `/usr/lib/howdy-island/howdy_island/` — application code
> - `/usr/bin/howdy-island` — launcher
> - `/usr/lib/systemd/user/howdy-island.service` — per-user service
> - `/usr/share/howdy-island/style.css` — theme template

After installing from any channel, each user enables the service once:

```bash
systemctl --user enable --now howdy-island.service
```

---

## 1. Fedora COPR

COPR is Fedora's free build & hosting service. End users then do:

```bash
sudo dnf copr enable sijuz/howdy-island
sudo dnf install howdy-island
```

### One-time setup

1. Sign in at <https://copr.fedorainfracloud.org/> with your Fedora account
   (FAS). Create one at <https://accounts.fedoraproject.org/> if needed.
2. **New Project** → name it `howdy-island`.
   - Under **Chroots**, tick the targets you want (e.g. `fedora-rawhide`,
     `fedora-41`, `fedora-40`).
3. Open the project → **Packages** → **New package** → method **SCM**:
   - **Clone url:** `https://github.com/sijuz/howdy-island`
   - **Committish:** `main`
   - **Subdirectory:** *(leave empty)*
   - **Spec File:** `packaging/howdy-island.spec`
   - **Build method:** `rpkg` (default) or `make_srpm` — `rpkg` works here.
4. Click **Build** (or **Build packages** from the package page). COPR downloads
   `Source0` automatically via `spectool`.

### Automatic rebuilds on push (optional)

In the COPR package settings enable **Auto-rebuild** and add the COPR webhook to
the GitHub repo (Settings → Webhooks). Every push then rebuilds the package.

### Local sanity check before uploading

```bash
# from the repo root
VERSION=0.1.0
git archive --format=tar.gz --prefix="howdy-island-${VERSION}/" \
    -o "/tmp/howdy-island-${VERSION}.tar.gz" HEAD
rpmbuild -ba packaging/howdy-island.spec \
    --define "_sourcedir /tmp" \
    --define "_topdir $(mktemp -d)"
```

---

## 2. openSUSE Build Service (OBS) — Debian/Ubuntu (and more)

OBS builds **both** `.deb` and `.rpm` from one place and hosts an APT/DNF repo.
End users on Ubuntu/Debian then do something like:

```bash
echo 'deb http://download.opensuse.org/repositories/home:/sijuz/xUbuntu_24.04/ /' \
  | sudo tee /etc/apt/sources.list.d/howdy-island.list
curl -fsSL https://download.opensuse.org/repositories/home:sijuz/xUbuntu_24.04/Release.key \
  | gpg --dearmor | sudo tee /etc/apt/trusted.gpg.d/howdy-island.gpg > /dev/null
sudo apt update
sudo apt install howdy-island
```

(The exact URL is shown by OBS once the repo is published — replace `sijuz`
and the distro/version to match.)

### One-time setup

1. Create an account at <https://build.opensuse.org/>.
2. Install the OBS CLI and log in:

   ```bash
   sudo dnf install osc      # Fedora
   # or: sudo apt install osc
   osc -A https://api.opensuse.org ls          # prompts for credentials once
   ```

3. Create the package in your home project and check it out:

   ```bash
   osc -A https://api.opensuse.org meta pkg -e home:sijuz howdy-island
   osc -A https://api.opensuse.org co home:sijuz howdy-island
   cd home:sijuz/howdy-island
   ```

4. Copy the packaging files into the checkout. The Debian files use OBS's
   `debian.<name>` flat naming; OBS reconstructs `debian/` from them:

   ```bash
   REPO=/path/to/howdy-island
   cp "$REPO"/packaging/obs/_service .
   cp "$REPO"/packaging/howdy-island.spec .
   cp "$REPO"/packaging/obs/debian.control   .
   cp "$REPO"/packaging/obs/debian.rules     .
   cp "$REPO"/packaging/obs/debian.changelog .
   cp "$REPO"/packaging/obs/debian.copyright .
   osc add _service *.spec debian.*
   osc commit -m "howdy-island 0.1.0"
   ```

5. In the OBS web UI for the package, **Add repositories** (e.g.
   `Debian 12`, `xUbuntu_24.04`, `Fedora 41`). OBS runs `_service` to fetch the
   source tarball, then builds with the spec (RPM targets) and the `debian.*`
   files (DEB targets).

### Releasing a new version

Bump the version in three places, then re-commit:

- `packaging/howdy-island.spec` → `Version:`
- `packaging/obs/debian.changelog` → new top entry
- `packaging/obs/_service` → the tag in `path` and the `filename`

---

## 3. Why not Flatpak?

`howdy-island` reads the systemd journal and `/proc` to detect Howdy activity,
cooperates with Howdy/PAM, and draws a Wayland **layer-shell** overlay. The
Flatpak sandbox blocks or complicates all of these, so a native package is the
correct distribution model here.
