#!/usr/bin/env bash
#
# howdy-island installer.
#
# Installs runtime dependencies (via your distro's package manager, with sudo),
# copies the package into ~/.local/share/howdy-island, and enables a per-user
# systemd service so the overlay starts with your graphical session.
#
# Usage:  ./install.sh
#
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/howdy-island"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE="howdy-island.service"

info()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn()  { printf '\033[1;33m[!]\033[0m %s\n' "$*"; }
die()   { printf '\033[1;31m[x]\033[0m %s\n' "$*" >&2; exit 1; }

# --- 1. Install runtime dependencies ---------------------------------------

install_deps() {
  local id_like="" id=""
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    id="${ID:-}"; id_like="${ID_LIKE:-}"
  fi

  local family="$id $id_like"
  info "Installing runtime dependencies (you may be prompted for your password)"

  case "$family" in
    *fedora*|*rhel*|*centos*)
      sudo dnf install -y python3-gobject python3-cairo gtk3 gtk-layer-shell
      ;;
    *debian*|*ubuntu*)
      sudo apt-get update
      sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 \
        gir1.2-gtklayershell-0.1
      ;;
    *arch*)
      sudo pacman -S --needed --noconfirm python-gobject python-cairo gtk3 \
        gtk-layer-shell
      ;;
    *suse*|*opensuse*)
      sudo zypper install -y python3-gobject python3-gobject-cairo \
        "typelib(Gtk)=3.0" "typelib(GtkLayerShell)"
      ;;
    *)
      warn "Unknown distro ($id). Please install these yourself:"
      warn "  PyGObject, pycairo, GTK 3, and gtk-layer-shell (with its GI typelib)."
      ;;
  esac
}

# --- 2. Verify the GTK layer-shell binding is importable -------------------

verify_bindings() {
  info "Verifying GTK / layer-shell Python bindings"
  if ! python3 - <<'PY'
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")
from gi.repository import Gtk, GtkLayerShell  # noqa: F401
PY
  then
    die "GtkLayerShell typelib not importable. Install the gtk-layer-shell \
GObject-Introspection typelib for your distro and retry."
  fi
}

# --- 3. Deploy application files -------------------------------------------

deploy() {
  info "Installing application to $APP_DIR"
  rm -rf "$APP_DIR/howdy_island"
  mkdir -p "$APP_DIR"
  cp -a "$REPO_DIR/src/howdy_island" "$APP_DIR/howdy_island"

  info "Installing user service to $UNIT_DIR/$SERVICE"
  mkdir -p "$UNIT_DIR"
  cp -a "$REPO_DIR/systemd/$SERVICE" "$UNIT_DIR/$SERVICE"
}

# --- 4. Enable the service --------------------------------------------------

enable_service() {
  info "Enabling and starting the user service"
  systemctl --user daemon-reload
  systemctl --user enable --now "$SERVICE"
}

main() {
  command -v python3 >/dev/null || die "python3 is required."

  if ! command -v howdy >/dev/null 2>&1; then
    warn "Howdy does not appear to be installed. howdy-island only shows an"
    warn "indicator for Howdy's face authentication, so install Howdy first."
  fi

  install_deps
  verify_bindings
  deploy
  enable_service

  info "Done. Test the overlay any time with:"
  printf '      PYTHONPATH=%q python3 -m howdy_island --simulate cycle\n' "$APP_DIR"
  info "Service status:  systemctl --user status $SERVICE"
}

main "$@"
