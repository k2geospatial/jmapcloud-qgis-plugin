# -----------------------------------------------------------
# 2026-09-08
# Copyright (C) 2026 K2 Geospatial
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 3
# #
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# -----------------------------------------------------------

from qgis.PyQt.QtCore import QObject, QTimer

STEP_INACTIVITY_TIMEOUT_MS = 5 * 60 * 1000
# The server analyzers are polled up to 200 times every 2.5 seconds, so a step that
# waits on one needs more room than the others before it is declared stalled.
ANALYZED_STEP_INACTIVITY_TIMEOUT_MS = 11 * 60 * 1000


class StepGuard(QObject):
    """
    Guarantees that a step of a pipeline always ends, and ends only once.

    A step normally moves to the next one when its task emits "I am done". If that
    never happens, the pipeline stops silently and the user is left with a frozen
    progress bar. This guard watches three things and keeps the first one to happen:

        success -> connect to the task's completion signal
        failure -> connect to the task's failure signals
        touch   -> connect to the task's progress signal, to say it is still alive

    Anything arriving after the first one is ignored, so the step can never be
    finished twice. If nothing happens at all for `inactivity_timeout_ms`, the guard
    declares the step stalled and reports a failure itself.
    """

    def __init__(
        self,
        name: str,
        on_success: callable,
        on_failure: callable,
        inactivity_timeout_ms: int,
        parent: QObject = None,
    ):
        super().__init__(parent)
        self._name = name
        self._on_success = on_success
        self._on_failure = on_failure
        self._done = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(inactivity_timeout_ms)
        self._timer.timeout.connect(self._inactivity_expired)
        self._timer.start()

    def success(self, *args):
        if self._consume():
            self._on_success(*args)

    def failure(self, message: str = None):
        if self._consume():
            self._on_failure(message or self.tr("Step {} failed").format(self._name))

    def touch(self, *args):
        """Restart the inactivity timer. Connect to any signal that shows progress."""
        if not self._done:
            self._timer.start()

    def abandon(self):
        """Stop watching, without reporting anything. Used when the user cancels."""
        self._consume()

    def is_done(self) -> bool:
        return self._done

    def _inactivity_expired(self):
        if self._consume():
            self._on_failure(
                self.tr("Step {} stopped responding after {} seconds without progress").format(
                    self._name, round(self._timer.interval() / 1000)
                )
            )

    def _consume(self) -> bool:
        if self._done:
            return False
        self._done = True
        self._timer.stop()
        return True
