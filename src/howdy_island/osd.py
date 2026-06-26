"""The on-screen overlay: a Dynamic Island–style pill at the top-center.

Implemented with GTK 3 + ``gtk-layer-shell`` so the surface floats above
normal windows as a Wayland layer-shell overlay (works on KWin, sway,
Hyprland, …). The overlay is click-through and never takes keyboard focus.

Note: by design the secure lock screen / login greeter cannot be drawn over
on Wayland, so this OSD only appears for in-session prompts (sudo, polkit,
application authentication).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("GtkLayerShell", "0.1")

import cairo  # noqa: E402  (provided by pycairo / PyGObject)
from gi.repository import GLib, Gtk, GtkLayerShell  # noqa: E402

from .config import Config
from .events import ScanEvent, ScanState


def _user_style_path() -> Optional[Path]:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return Path(base) / "howdy-island" / "style.css"


def _build_css(config: Config) -> bytes:
    """Generate the default stylesheet, honouring configurable timings."""

    return f"""
    window {{
        background: transparent;
    }}
    .island {{
        background-color: rgba(22, 22, 24, 0.92);
        border-radius: 24px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 10px 20px;
        opacity: 0;
        transition: opacity {config.animation_ms}ms ease;
    }}
    .island.shown {{
        opacity: 1;
    }}
    .island label {{
        color: #ffffff;
        font-size: 14px;
        font-weight: 600;
    }}
    .island .glyph {{
        font-size: 17px;
        font-weight: 800;
    }}
    .island.success .glyph {{ color: #34c759; }}
    .island.failure .glyph {{ color: #ff453a; }}
    .island.scanning label {{ color: #e8e8ed; }}
    """.encode("utf-8")


class IslandOsd:
    """Renders :class:`ScanEvent` transitions as an animated overlay pill."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._visible = False
        self._tween_source: Optional[int] = None
        self._hide_delay_source: Optional[int] = None
        self._finish_hide_source: Optional[int] = None
        self._reveal_source: Optional[int] = None

        self._build_ui()
        self._load_css()

    # -- public API --------------------------------------------------------

    def handle_event(self, event: ScanEvent) -> None:
        if event.state is ScanState.SCANNING:
            self._show(
                css_class="scanning",
                text=self._config.scanning_text,
                glyph=None,
                spinning=True,
                auto_hide_ms=None,
            )
        elif event.state is ScanState.SUCCESS:
            text = (
                self._config.success_text.format(user=event.user)
                if event.user
                else self._config.success_text_no_user
            )
            self._show(
                css_class="success",
                text=text,
                glyph="\u2713",  # ✓
                spinning=False,
                auto_hide_ms=self._config.success_timeout_ms,
            )
        elif event.state is ScanState.FAILURE:
            self._show(
                css_class="failure",
                text=self._config.failure_text,
                glyph="\u2715",  # ✕
                spinning=False,
                auto_hide_ms=self._config.failure_timeout_ms,
            )
        elif event.state is ScanState.HIDDEN:
            self._hide()

    # -- UI construction ---------------------------------------------------

    def _build_ui(self) -> None:
        self.window = Gtk.Window(type=Gtk.WindowType.TOPLEVEL)
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_app_paintable(True)

        # RGBA visual so the rounded corners are truly transparent.
        screen = self.window.get_screen()
        visual = screen.get_rgba_visual() if screen is not None else None
        if visual is not None:
            self.window.set_visual(visual)

        GtkLayerShell.init_for_window(self.window)
        GtkLayerShell.set_namespace(self.window, "howdy-island")
        GtkLayerShell.set_layer(self.window, GtkLayerShell.Layer.OVERLAY)
        # Anchor to the top edge only -> horizontally centered.
        GtkLayerShell.set_anchor(self.window, GtkLayerShell.Edge.TOP, True)
        GtkLayerShell.set_margin(
            self.window, GtkLayerShell.Edge.TOP, self._config.margin_top
        )
        GtkLayerShell.set_keyboard_mode(
            self.window, GtkLayerShell.KeyboardMode.NONE
        )

        self._root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self._root.get_style_context().add_class("island")

        self._spinner = Gtk.Spinner()
        self._glyph = Gtk.Label()
        self._glyph.get_style_context().add_class("glyph")
        self._label = Gtk.Label()

        self._root.pack_start(self._spinner, False, False, 0)
        self._root.pack_start(self._glyph, False, False, 0)
        self._root.pack_start(self._label, False, False, 0)

        self.window.add(self._root)

    def _load_css(self) -> None:
        screen = self.window.get_screen()
        if screen is None:
            return

        base = Gtk.CssProvider()
        base.load_from_data(_build_css(self._config))
        Gtk.StyleContext.add_provider_for_screen(
            screen, base, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )

        # Optional user override: ~/.config/howdy-island/style.css
        user_css = _user_style_path()
        if user_css is not None and user_css.is_file():
            override = Gtk.CssProvider()
            try:
                override.load_from_path(str(user_css))
            except GLib.Error:
                return
            Gtk.StyleContext.add_provider_for_screen(
                screen, override, Gtk.STYLE_PROVIDER_PRIORITY_USER
            )

    # -- show / hide -------------------------------------------------------

    def _show(
        self,
        css_class: str,
        text: str,
        glyph: Optional[str],
        spinning: bool,
        auto_hide_ms: Optional[int],
    ) -> None:
        self._cancel_pending_hide()

        ctx = self._root.get_style_context()
        for name in ("scanning", "success", "failure"):
            ctx.remove_class(name)
        ctx.add_class(css_class)

        self._label.set_text(text)

        if glyph is None:
            self._glyph.hide()
            self._glyph.set_text("")
        else:
            self._glyph.set_text(glyph)
            self._glyph.show()

        if spinning:
            self._spinner.show()
            self._spinner.start()
        else:
            self._spinner.stop()
            self._spinner.hide()

        self._reveal()

        if auto_hide_ms is not None:
            self._hide_delay_source = GLib.timeout_add(auto_hide_ms, self._on_auto_hide)

    def _reveal(self) -> None:
        margin = self._config.margin_top
        start_margin = margin - self._config.slide_distance

        if not self._visible:
            self._visible = True
            GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.TOP, start_margin)
            self._root.get_style_context().remove_class("shown")
            self.window.show_all()
            # Re-apply per-state widget visibility after show_all().
            self._sync_indicator_visibility()
            self._make_click_through()
            # Defer adding ".shown" so the opacity transition actually runs.
            self._reveal_source = GLib.timeout_add(10, self._begin_reveal_anim)
        else:
            self._sync_indicator_visibility()
            self._root.get_style_context().add_class("shown")
            self._animate_margin(start_margin, margin)

    def _begin_reveal_anim(self) -> bool:
        self._reveal_source = None
        self._root.get_style_context().add_class("shown")
        self._animate_margin(
            self._config.margin_top - self._config.slide_distance,
            self._config.margin_top,
        )
        return GLib.SOURCE_REMOVE

    def _on_auto_hide(self) -> bool:
        self._hide_delay_source = None
        self._hide()
        return GLib.SOURCE_REMOVE

    def _hide(self) -> None:
        self._cancel_pending_hide()
        if not self._visible:
            return
        self._root.get_style_context().remove_class("shown")
        self._animate_margin(
            self._config.margin_top,
            self._config.margin_top - self._config.slide_distance,
        )
        self._finish_hide_source = GLib.timeout_add(
            self._config.animation_ms + 60, self._finish_hide
        )

    def _finish_hide(self) -> bool:
        self._finish_hide_source = None
        self._visible = False
        self._spinner.stop()
        self.window.hide()
        return GLib.SOURCE_REMOVE

    # -- helpers -----------------------------------------------------------

    def _sync_indicator_visibility(self) -> None:
        if self._spinner.get_property("active"):
            self._spinner.show()
        else:
            self._spinner.hide()
        if self._glyph.get_text():
            self._glyph.show()
        else:
            self._glyph.hide()

    def _make_click_through(self) -> None:
        gdk_window = self.window.get_window()
        if gdk_window is not None:
            empty = cairo.Region()
            gdk_window.input_shape_combine_region(empty, 0, 0)

    def _animate_margin(self, start: int, end: int) -> None:
        if self._tween_source is not None:
            GLib.source_remove(self._tween_source)
            self._tween_source = None

        steps = max(1, self._config.animation_ms // 16)
        state = {"i": 0}

        def tick() -> bool:
            state["i"] += 1
            progress = state["i"] / steps
            eased = 1 - pow(1 - min(progress, 1.0), 3)  # ease-out cubic
            value = int(round(start + (end - start) * eased))
            GtkLayerShell.set_margin(self.window, GtkLayerShell.Edge.TOP, value)
            if state["i"] >= steps:
                self._tween_source = None
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        self._tween_source = GLib.timeout_add(16, tick)

    def _cancel_pending_hide(self) -> None:
        for attr in ("_hide_delay_source", "_finish_hide_source", "_reveal_source"):
            source = getattr(self, attr)
            if source is not None:
                GLib.source_remove(source)
                setattr(self, attr, None)
