#!/usr/bin/env bash
#
# Build distributable packages for howdy-island.
#
# Stages the application into a package root and (if `fpm` is available)
# produces a .deb and a .rpm in ./dist. Used both locally and by CI.
#
# Usage:  packaging/build.sh [VERSION]
#         VERSION defaults to the value in pyproject.toml.
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PKGROOT="$ROOT/build/pkgroot"
DIST="$ROOT/dist"

# Resolve version: explicit arg > pyproject.toml.
VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/pyproject.toml" | head -n1)"
fi
[[ -n "$VERSION" ]] || { echo "Could not determine version" >&2; exit 1; }

echo "==> Building howdy-island $VERSION"

# --- Stage the file tree ----------------------------------------------------

rm -rf "$PKGROOT"
install -d "$PKGROOT/usr/lib/howdy-island"
cp -a "$ROOT/src/howdy_island" "$PKGROOT/usr/lib/howdy-island/howdy_island"
# Drop any byte-compiled cruft.
find "$PKGROOT/usr/lib/howdy-island" -name '__pycache__' -type d -prune -exec rm -rf {} +

install -d "$PKGROOT/usr/bin"
cat > "$PKGROOT/usr/bin/howdy-island" <<'EOF'
#!/bin/sh
# Launcher for the system-packaged howdy-island.
export PYTHONPATH="/usr/lib/howdy-island${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m howdy_island "$@"
EOF
chmod 0755 "$PKGROOT/usr/bin/howdy-island"

install -d "$PKGROOT/usr/lib/systemd/user"
cat > "$PKGROOT/usr/lib/systemd/user/howdy-island.service" <<'EOF'
[Unit]
Description=howdy-island — face-scan OSD for Howdy
Documentation=https://github.com/sijuz/howdy-island
PartOf=graphical-session.target
After=graphical-session.target

[Service]
Type=simple
Environment=PYTHONUNBUFFERED=1
ExecStart=/usr/bin/howdy-island
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
EOF

install -d "$PKGROOT/usr/share/doc/howdy-island"
cp -a "$ROOT/README.md" "$ROOT/LICENSE" "$ROOT/data/style.css" \
  "$PKGROOT/usr/share/doc/howdy-island/"

echo "==> Staged tree:"
find "$PKGROOT" -mindepth 1 -printf '    %P\n' | sort

# --- Package with fpm (optional) -------------------------------------------

if ! command -v fpm >/dev/null 2>&1; then
  echo "==> 'fpm' not found: staged only (install fpm to build .deb/.rpm)."
  exit 0
fi

rm -rf "$DIST"
install -d "$DIST"

# Tell users to enable the per-user service after install.
AFTER_INSTALL="$(mktemp)"
cat > "$AFTER_INSTALL" <<'EOF'
#!/bin/sh
echo "howdy-island installed. Enable it for your user with:"
echo "    systemctl --user enable --now howdy-island.service"
EOF

common_args=(
  -s dir
  -n howdy-island
  -v "$VERSION"
  --license "GPL-3.0-or-later"
  --maintainer "sijuz"
  --url "https://github.com/sijuz/howdy-island"
  --description "Dynamic Island-style on-screen indicator for Howdy face authentication."
  --architecture all
  --after-install "$AFTER_INSTALL"
  -C "$PKGROOT"
)

echo "==> Building .deb"
fpm "${common_args[@]}" -t deb -p "$DIST/" \
  -d python3 \
  -d python3-gi \
  -d python3-gi-cairo \
  -d gir1.2-gtk-3.0 \
  -d gir1.2-gtklayershell-0.1 \
  .

echo "==> Building .rpm"
fpm "${common_args[@]}" -t rpm -p "$DIST/" \
  -d python3 \
  -d python3-gobject \
  -d python3-cairo \
  -d gtk3 \
  -d gtk-layer-shell \
  .

rm -f "$AFTER_INSTALL"

echo "==> Artifacts:"
ls -l "$DIST"
