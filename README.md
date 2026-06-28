# howdy-island

A **Dynamic Island–style on-screen indicator** for [Howdy](https://github.com/boltgolt/howdy)
face authentication on Linux. It shows a small animated pill at the top-center
of your screen while Howdy is scanning your face, and whether it succeeded or
failed — so face login stops feeling like "nothing is happening".

```
            ╭───────────────────────────────╮
            │  ◌  Scanning your face…        │
            ╰───────────────────────────────╯

            ╭───────────────────────────────╮
            │  ✓  Welcome back, sijuz        │
            ╰───────────────────────────────╯
```

> Howdy itself authenticates silently through PAM, with no visual feedback.
> `howdy-island` adds that feedback without touching Howdy or PAM.

## Important: where the indicator can appear

`howdy-island` runs inside your **desktop session**, so it shows the overlay for
in-session authentication prompts:

- ✅ `sudo` in a terminal
- ✅ polkit prompts (e.g. installing updates, mounting disks)
- ✅ application password dialogs that use Howdy

It **cannot** draw over the **lock screen** or the **login/greeter screen** on
Wayland. Those are secure, isolated surfaces and the compositor does not allow
normal windows on top of them (this is also why Howdy's own GTK UI fails there).
If you need feedback on the lock screen specifically, that is not currently
possible on KDE/Wayland without patching the lock-screen theme.

## How it works

Howdy exposes no API, so `howdy-island` infers state from two cheap, read-only
signals:

1. **Scan started** — while authenticating, `pam_howdy` runs
   `python3 .../howdy/compare.py`. The daemon watches `/proc` for that process.
2. **Result** — `pam_howdy` logs its outcome to the systemd journal
   (`Identified face as …`, `Login approved`, `Failure, …`). The daemon follows
   the journal filtered to that identifier.

These feed a small state machine that drives a GTK 3 +
[`gtk-layer-shell`](https://github.com/wmww/gtk-layer-shell) overlay
(`wlr-layer-shell`), which works on KWin, sway, Hyprland and other compatible
compositors.

## Requirements

- A working **Howdy** setup (the IR camera enrolled and face login working).
- A Wayland compositor implementing `wlr-layer-shell` (KDE Plasma / KWin, sway,
  Hyprland, …).
- **GTK 3**, **PyGObject**, **pycairo**, and **gtk-layer-shell** (with its
  GObject-Introspection typelib).
- Read access to the system journal (typically: be in the `wheel`, `adm`, or
  `systemd-journal` group).

## Install

### From your package manager (repositories)

The recommended way — install and get updates through your package manager.

**Fedora (COPR):**

```bash
sudo dnf copr enable sijuz/howdy-island
sudo dnf install howdy-island
```

**Ubuntu / Debian (openSUSE Build Service):** add the repo shown on the
project's [OBS page](https://build.opensuse.org/), then `sudo apt install
howdy-island`.

> Maintainers: see [`docs/PACKAGING.md`](docs/PACKAGING.md) for how these
> repositories are set up and how to publish a new version.

### From a release (prebuilt packages)

Download the latest `.deb` (Ubuntu/Debian) or `.rpm` (Fedora) from the
[Releases page](https://github.com/sijuz/howdy-island/releases), then:

```bash
# Ubuntu / Debian
sudo apt install ./howdy-island_*_all.deb

# Fedora
sudo dnf install ./howdy-island-*.noarch.rpm
```

After installing, enable the per-user service (this is a *user* service, so it
is enabled per user, not system-wide):

```bash
systemctl --user enable --now howdy-island.service
```

### From source

```bash
git clone https://github.com/sijuz/howdy-island.git
cd howdy-island
./install.sh
```

`install.sh` installs the runtime dependencies for your distro (using `sudo`
only for the package manager), copies the app to
`~/.local/share/howdy-island`, and enables a per-user systemd service.

Verify it is running:

```bash
systemctl --user status howdy-island.service
```

### Manual install

```bash
# 1. Dependencies (Fedora example)
sudo dnf install -y python3-gobject python3-cairo gtk3 gtk-layer-shell

# 2. Run directly from the repo
PYTHONPATH=src python3 -m howdy_island
```

## Try it without Howdy

Preview the overlay (great for theming or screenshots):

```bash
PYTHONPATH=src python3 -m howdy_island --simulate cycle
# or: --simulate scanning | success | failure
```

## Configuration

Optional. Create `~/.config/howdy-island/config.ini`:

```ini
[osd]
margin_top = 28
scanning_text = Scanning your face…
success_text = Welcome back, {user}
success_text_no_user = Face recognized
failure_text = Face not recognized
success_timeout_ms = 1400
failure_timeout_ms = 2000
animation_ms = 180
slide_distance = 14

[detector]
poll_interval_ms = 150
result_grace_ms = 700
```

### Theming

Copy [`data/style.css`](data/style.css) to `~/.config/howdy-island/style.css`
and tweak. It is layered on top of the built-in style, so you only override
what you want. The overlay is a `GtkBox.island` with a state class
(`.scanning` / `.success` / `.failure`), containing a spinner, a `.glyph`
label, and the message label.

## Troubleshooting

**Nothing appears for `sudo`.** Confirm the service is running
(`systemctl --user status howdy-island.service`) and that Howdy is actually
being invoked (you should see `pam_howdy` lines in
`journalctl SYSLOG_IDENTIFIER=pam_howdy`).

**`ValueError: Namespace GtkLayerShell not available`.** Install the
gtk-layer-shell GObject-Introspection typelib (e.g. `gtk-layer-shell` on
Fedora/Arch, `gir1.2-gtklayershell-0.1` on Debian/Ubuntu).

**The overlay never shows a result, only "Scanning…".** You likely lack journal
read access. Add your user to a journal-readable group, e.g.
`sudo usermod -aG systemd-journal "$USER"`, then re-login.

**It shows on the lock screen partially / not at all.** Expected — see
[*Important*](#important-where-the-indicator-can-appear) above.

## Uninstall

```bash
./uninstall.sh
```

## License

[GPL-3.0-or-later](LICENSE).

## Acknowledgements

- [Howdy](https://github.com/boltgolt/howdy) — Windows Hello–style face
  authentication for Linux.
- [gtk-layer-shell](https://github.com/wmww/gtk-layer-shell) — layer-shell
  support for GTK.
