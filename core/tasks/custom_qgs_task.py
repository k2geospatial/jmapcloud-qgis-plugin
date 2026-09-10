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

import functools
import traceback

from qgis.core import Qgis, QgsFeedback, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import QObject, pyqtSignal

MESSAGE_CATEGORY = "Custom JMap Cloud Task"


def _guarded_run(run: callable) -> callable:
    """
    Wrap a task's run() so no exception escapes it. An escaping exception would
    leave the task without emitting its completion signal, stalling the caller.
    """

    @functools.wraps(run)
    def wrapper(self, *args, **kwargs):
        try:
            return run(self, *args, **kwargs)
        except Exception as exception:
            self.handle_unexpected_exception(exception)
            return False

    wrapper._jmc_guarded = True
    return wrapper


class UnexpectedExceptionMixin:
    """Records an exception that escaped a guarded run()."""

    def __init_subclass__(cls, **kwargs):
        """Guard every run() declared by a subclass."""
        super().__init_subclass__(**kwargs)
        run = cls.__dict__.get("run")
        if run is not None and not getattr(run, "_jmc_guarded", False):
            cls.run = _guarded_run(run)

    def handle_unexpected_exception(self, exception: Exception, category: str = MESSAGE_CATEGORY):
        QgsMessageLog.logMessage(traceback.format_exc(), category, Qgis.MessageLevel.Critical)
        self.add_exception(exception)
        self.error_occur(
            self.tr("Unexpected error in {}: {}").format(
                getattr(self, "name", type(self).__name__), exception
            ),
            category,
        )


class CustomQgsTask(UnexpectedExceptionMixin, QgsTask):
    error_occurred = pyqtSignal(str)
    step_title_changed = pyqtSignal(str)

    name: str
    exceptions: list[Exception]
    current_step: int
    total_steps: int
    feedback: QgsFeedback

    def __init__(
        self, name: str, flag: QgsTask.Flag = None, total_steps: int = 0, feedback: QgsFeedback = None, **kwargs
    ) -> None:
        if flag is None:
            super().__init__(name, **kwargs)
        else:
            super().__init__(name, flag, **kwargs)
        self.name = name
        self.exceptions = []
        self.current_step = 0
        self.total_steps = total_steps
        if feedback:
            self.feedback = feedback
            self.progressChanged.connect(self.feedback.setProgress)
            self.feedback.canceled.connect(self.cancel)

    def cancel(self):
        QgsMessageLog.logMessage(self.tr("{} was canceled").format(self.description()), MESSAGE_CATEGORY, Qgis.MessageLevel.Info)
        super().cancel()

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(
                self.tr("{} completed successfully").format(self.description()), MESSAGE_CATEGORY, Qgis.MessageLevel.Success
            )
        else:
            if len(self.exceptions) == 0:
                QgsMessageLog.logMessage(
                    self.tr(
                        """
                        {} not successful but without 
                        exception (probably the task was manually 
                        canceled by the user)
                        """
                    ).format(self.name),
                    MESSAGE_CATEGORY,
                    Qgis.MessageLevel.Warning,
                )
            else:
                QgsMessageLog.logMessage(
                    self._exceptions_message(), MESSAGE_CATEGORY, Qgis.MessageLevel.Critical
                )

        super().finished(result)

    def _exceptions_message(self) -> str:
        message = "{} Exception:".format(self.name)
        for exception in self.exceptions:
            message += "\n{}".format(exception)
        return message

    def debug(self, message: str):
        QgsMessageLog.logMessage(message, MESSAGE_CATEGORY, Qgis.MessageLevel.Info)

    def set_total_steps(self, total_steps: int):
        self.total_steps = total_steps

    def next_steps(self, step_title: str = None):
        self.step_title_changed.emit(step_title)
        self.current_step += 1
        self.setProgress(self.current_step / self.total_steps * 100)

    def add_exception(self, exception: Exception):
        self.exceptions.append(exception)

    def error_occur(self, message: str, category: str = MESSAGE_CATEGORY):
        QgsMessageLog.logMessage(message, category, Qgis.MessageLevel.Critical)
        self.error_occurred.emit(message)

    @classmethod
    def fromFunction(
        cls,
        name: str,
        function: callable,
        *args,
        on_finished: callable = None,
        flags=2,
        total_steps: int = 0,
        feedback: QgsFeedback = None,
        **kwargs,
    ) -> "CustomQgsTask":

        instance = super().fromFunction(name, function, *args, on_finished=on_finished, flags=flags, **kwargs)
        instance.__class__ = cls
        instance.name = name
        instance.exceptions = []
        instance.current_step = 0
        instance.total_steps = total_steps
        if feedback:
            instance.feedback = feedback
            instance.progressChanged.connect(instance.feedback.setProgress)
            instance.feedback.canceled.connect(instance.cancel)
        return instance


class CustomTaskManager(UnexpectedExceptionMixin, QObject):
    error_occurred = pyqtSignal(str)
    run_failed = pyqtSignal(str)
    step_title_changed = pyqtSignal(str)
    canceled = pyqtSignal()
    progress_changed = pyqtSignal(float)
    tasks_completed = pyqtSignal(object)

    name: str
    exceptions: list[Exception]
    current_step: int
    total_steps: int
    is_cancel: bool
    tasks: list[CustomQgsTask]

    def __init__(self, name: str, total_steps: int = 0, feedback: QgsFeedback = None) -> None:
        super().__init__()
        self.name = name
        self.exceptions = []
        self.current_step = 0
        self.total_steps = total_steps
        self.is_cancel = False
        self.tasks = []
        if feedback:
            self.feedback = feedback
            self.progress_changed.connect(self.feedback.setProgress)
            self.feedback.canceled.connect(self.cancel)

    def cancel(self):
        QgsMessageLog.logMessage(self.tr("{} was canceled").format(self.name), MESSAGE_CATEGORY, Qgis.MessageLevel.Info)
        self.is_cancel = True
        self.canceled.emit()

    def is_canceled(self) -> bool:
        return self.is_cancel

    def start(self):
        result = False
        try:
            result = self.run()
        except Exception as e:
            result = False
            self.exceptions.append(e)
        self.finished(result)

    def run(self) -> bool:
        return True

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage("{} completed successfully".format(self.name), MESSAGE_CATEGORY, Qgis.MessageLevel.Success)
        else:
            if len(self.exceptions) == 0:
                QgsMessageLog.logMessage(
                    self.tr(
                        """
                        {} not successful but without 
                        exception (probably the task was manually 
                        canceled by the user)
                        """
                    ).format(self.name),
                    MESSAGE_CATEGORY,
                    Qgis.MessageLevel.Warning,
                )
            else:
                QgsMessageLog.logMessage(
                    self._exceptions_message(), MESSAGE_CATEGORY, Qgis.MessageLevel.Critical
                )
                self.run_failed.emit(self.tr("{} did not complete").format(self.name))

    def _exceptions_message(self) -> str:
        message = "{} Exception:".format(self.name)
        for exception in self.exceptions:
            message += "\n{}".format(exception)
        return message

    def set_total_steps(self, total_steps: int):
        self.total_steps = total_steps

    def next_steps(self, step_title: str = None):
        self.step_title_changed.emit(step_title)
        self.current_step += 1
        self.progress_changed.emit(self.current_step / self.total_steps * 100)

    def add_exception(self, exception: Exception):
        self.exceptions.append(exception)

    def error_occur(self, message: str, category: str = MESSAGE_CATEGORY):
        QgsMessageLog.logMessage(message, category, Qgis.MessageLevel.Critical)
        self.error_occurred.emit(message)
