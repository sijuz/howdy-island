#!/usr/bin/env bash
#
# howdy-island uninstaller. Removes the user service and application files.
# Runtime dependencies (GTK, gtk-layer-shell, PyGObject) are left installed.
#
set -euo pipefail

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/howdy-island"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SERVICE="howdy-island.service"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

info "Stopping and disabling the user service"
systemctl --user disable --now "$SERVICE" 2>/dev/null || true
rm -f "$UNIT_DIR/$SERVICE"
systemctl --user daemon-reload 2>/dev/null || true

info "Removing application files from $APP_DIR"
rm -rf "$APP_DIR/howdy_island"
rmdir "$APP_DIR" 2>/dev/null || true

info "Done. Your config at ~/.config/howdy-island (if any) was left untouched."
info "To remove runtime deps, uninstall gtk-layer-shell via your package manager."
