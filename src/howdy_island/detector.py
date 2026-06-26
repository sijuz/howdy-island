"""Detects Howdy face-authentication activity and emits high-level events.

Howdy itself exposes no IPC, so we infer state from two cheap, read-only
signals available to a normal user session:

1. **Scan start** — ``pam_howdy`` spawns ``python3 .../howdy/compare.py`` for
   the duration of a scan. We watch ``/proc`` for that command line.
2. **Scan result** — ``pam_howdy`` logs its outcome to the system journal
   (e.g. ``Identified face as <user>``, ``Login approved``, ``Failure, ...``).
   We follow the journal filtered to that identifier.

Both signals are combined into a small state machine that emits
:class:`~howdy_island.events.ScanEvent` objects via a callback.
"""

from __future__ import annotations

import os
import re
from typing import Callable, Optional

import gi

from gi.repository import Gio, GLib

from .config import Config
from .events import ScanEvent, ScanState

# Command-line fragment of the process Howdy runs while scanning.
_COMPARE_CMD_FRAGMENT = "howdy/compare.py"

# MESSAGE patterns produced by pam_howdy (see Howdy's src/pam sources).
_RE_IDENTIFIED = re.compile(r"Identified face as (?P<user>.+)")
_RE_LOGIN_OK = re.compile(r"^Login approved\b")
_FAILURE_PATTERNS = (
    re.compile(r"^Failure,"),
    re.compile(r"image too dark", re.IGNORECASE),
    re.compile(r"timeout reached", re.IGNORECASE),
    re.compile(r"no face model", re.IGNORECASE),
    re.compile(r"not possible to open camera", re.IGNORECASE),
)

EventCallback = Callable[[ScanEvent], None]


class HowdyDetector:
    """Watches Howdy activity and reports state transitions.

    Parameters
    ----------
    on_event:
        Called (on the GLib main loop thread) for every state transition.
    config:
        Runtime configuration controlling poll interval and grace period.
    """

    def __init__(self, on_event: EventCallback, config: Config) -> None:
        self._on_event = on_event
        self._config = config

        self._state: ScanState = ScanState.HIDDEN
        self._pending_user: Optional[str] = None
        self._was_scanning_proc = False

        self._poll_source: Optional[int] = None
        self._grace_source: Optional[int] = None
        self._journal_proc: Optional[Gio.Subprocess] = None
        self._journal_stream: Optional[Gio.DataInputStream] = None

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        self._start_journal()
        self._poll_source = GLib.timeout_add(
            self._config.poll_interval_ms, self._poll_compare_process
        )

    def stop(self) -> None:
        if self._poll_source is not None:
            GLib.source_remove(self._poll_source)
            self._poll_source = None
        self._cancel_grace()
        if self._journal_proc is not None:
            self._journal_proc.force_exit()
            self._journal_proc = None

    # -- journal following -------------------------------------------------

    def _start_journal(self) -> None:
        argv = [
            "journalctl",
            "--follow",
            "--lines", "0",
            "--output", "cat",
            "SYSLOG_IDENTIFIER=pam_howdy",
        ]
        try:
            self._journal_proc = Gio.Subprocess.new(
                argv,
                Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE,
            )
        except GLib.Error:
            # journalctl unavailable: fall back to process-only detection.
            self._journal_proc = None
            return

        self._journal_stream = Gio.DataInputStream.new(
            self._journal_proc.get_stdout_pipe()
        )
        self._queue_read()

    def _queue_read(self) -> None:
        if self._journal_stream is None:
            return
        self._journal_stream.read_line_async(
            GLib.PRIORITY_DEFAULT, None, self._on_journal_line
        )

    def _on_journal_line(self, stream: Gio.DataInputStream, result: Gio.AsyncResult) -> None:
        try:
            data, _length = stream.read_line_finish(result)
        except GLib.Error:
            data = None

        if data is None:
            # EOF: journalctl exited. Try to re-establish shortly.
            self._journal_stream = None
            self._journal_proc = None
            GLib.timeout_add_seconds(2, self._restart_journal)
            return

        if isinstance(data, (bytes, bytearray)):
            line = bytes(data).decode("utf-8", "replace").strip()
        else:
            line = str(data).strip()

        if line:
            self._handle_message(line)
        self._queue_read()

    def _restart_journal(self) -> bool:
        if self._journal_proc is None:
            self._start_journal()
        return GLib.SOURCE_REMOVE

    # -- message handling --------------------------------------------------

    def _handle_message(self, line: str) -> None:
        identified = _RE_IDENTIFIED.search(line)
        if identified:
            self._pending_user = identified.group("user").strip()
            self._emit_result(ScanState.SUCCESS, user=self._pending_user)
            return

        if _RE_LOGIN_OK.search(line):
            self._emit_result(ScanState.SUCCESS, user=self._pending_user)
            return

        for pattern in _FAILURE_PATTERNS:
            if pattern.search(line):
                self._emit_result(ScanState.FAILURE, reason=line)
                return

    # -- compare.py process polling ---------------------------------------

    @staticmethod
    def _compare_process_running() -> bool:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                with open(f"/proc/{entry}/cmdline", "rb") as handle:
                    cmdline = handle.read().replace(b"\x00", b" ").decode(
                        "utf-8", "replace"
                    )
            except (FileNotFoundError, ProcessLookupError, PermissionError, OSError):
                continue
            if _COMPARE_CMD_FRAGMENT in cmdline:
                return True
        return False

    def _poll_compare_process(self) -> bool:
        running = self._compare_process_running()
        if running and not self._was_scanning_proc:
            self._on_scan_start()
        elif not running and self._was_scanning_proc:
            self._on_scan_end()
        self._was_scanning_proc = running
        return GLib.SOURCE_CONTINUE

    def _on_scan_start(self) -> None:
        self._cancel_grace()
        self._pending_user = None
        if self._state is not ScanState.SCANNING:
            self._set_state(ScanEvent(ScanState.SCANNING))

    def _on_scan_end(self) -> None:
        # If the scan finished without a journal result yet, wait briefly for
        # the result line; otherwise treat it as cancelled and hide.
        if self._state is ScanState.SCANNING and self._grace_source is None:
            self._grace_source = GLib.timeout_add(
                self._config.result_grace_ms, self._on_grace_elapsed
            )

    def _on_grace_elapsed(self) -> bool:
        self._grace_source = None
        if self._state is ScanState.SCANNING:
            self._set_state(ScanEvent(ScanState.HIDDEN))
        return GLib.SOURCE_REMOVE

    # -- helpers -----------------------------------------------------------

    def _emit_result(
        self, state: ScanState, user: Optional[str] = None, reason: Optional[str] = None
    ) -> None:
        self._cancel_grace()
        if state is ScanState.SUCCESS and self._state is ScanState.SUCCESS:
            return  # de-duplicate the "Identified" + "Login approved" pair
        self._set_state(ScanEvent(state, user=user, reason=reason))

    def _set_state(self, event: ScanEvent) -> None:
        self._state = event.state
        self._on_event(event)

    def _cancel_grace(self) -> None:
        if self._grace_source is not None:
            GLib.source_remove(self._grace_source)
            self._grace_source = None
