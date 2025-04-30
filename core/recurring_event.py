# -----------------------------------------------------------
# 2025-04-29
# Copyright (C) 2025 K2 Geospatial
# -----------------------------------------------------------
# Licensed under the terms of GNU GPL 3
# #
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
# -----------------------------------------------------------

from qgis.PyQt.QtCore import (
    QMutex,
    QMutexLocker,
    Qt,
    QThread,
    QWaitCondition,
    pyqtSignal,
)


class RecurringEvent(QThread):
    event_triggered = pyqtSignal()
    call_count_exceeded = pyqtSignal()

    def __init__(self, interval: float, callback: callable, call_on_first_run: bool = False, call_count: int = -1):
        """
        Constructor.

        :param interval: the interval in second
        :param callback: a callable that will be called every interval
        :param call_on_first_run: if True, the callback will be called immediately
        :param call_count: number of times the callback will be called. If < 0, the callback will be called forever until stopped. default -1 (until stopped)
        """
        super().__init__()
        self.interval = int(interval * 1000)
        self.callback = callback
        self.call_on_first_run = call_on_first_run
        self.call_count = call_count
        self._stop_event = False
        self.cond = QWaitCondition()
        self.mutex = QMutex()

        self.event_triggered.connect(self.callback, Qt.QueuedConnection)  # execute the callback in the main thread

    def run(self):
        """
        This method is called when the thread method start() is called. It emits a signal after a given interval.
        If self.call_on_first_run is True, it emits the signal immediately.

        :return: None
        """

        if self.call_count == 0:
            self.call_count_exceeded.emit()
            return
        if self.call_on_first_run:
            self.event_triggered.emit()
            self.call_count -= 1

        while not self._stop_event:
            if self.call_count == 0:
                self.call_count_exceeded.emit()
                break
            with QMutexLocker(self.mutex):
                if self._stop_event:
                    break
                self.cond.wait(self.mutex, self.interval)

            if self._stop_event:
                break
            self.event_triggered.emit()
            self.call_count -= 1

    def stop(self):
        """
        Stop the thread and wait for it to finish.
        """
        with QMutexLocker(self.mutex):
            self._stop_event = True
        self.cond.wakeAll()

        if self.isRunning():
            self.quit()
            self.wait()
