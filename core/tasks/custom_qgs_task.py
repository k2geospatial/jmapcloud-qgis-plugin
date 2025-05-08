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

from qgis.core import Qgis, QgsFeedback, QgsMessageLog, QgsTask
from qgis.PyQt.QtCore import QObject, pyqtSignal

MESSAGE_CATEGORY = "Custom JMap Cloud Task"


class CustomQgsTask(QgsTask):
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
        QgsMessageLog.logMessage(self.tr("{} was canceled").format(self.description()), MESSAGE_CATEGORY, Qgis.Info)
        super().cancel()

    def finished(self, result):
        if result:
            QgsMessageLog.logMessage(
                self.tr("{} completed successfully").format(self.description()), MESSAGE_CATEGORY, Qgis.Success
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
                    Qgis.Warning,
                )
            else:
                message = f"{self.name} Exception:"
                for exception in self.exceptions:
                    message += f"\n{exception}"
                QgsMessageLog.logMessage(message, MESSAGE_CATEGORY, Qgis.Critical)
                raise Exception(message)

        super().finished(result)

    def set_total_steps(self, total_steps: int):
        self.total_steps = total_steps

    def next_steps(self, step_title: str = None):
        self.step_title_changed.emit(step_title)
        self.current_step += 1
        self.setProgress(self.current_step / self.total_steps * 100)

    def add_exception(self, exception: Exception):
        self.exceptions.append(exception)

    def error_occur(self, message: str, category: str = MESSAGE_CATEGORY):
        QgsMessageLog.logMessage(message, category, Qgis.Critical)
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


class CustomTaskManager(QObject):
    error_occurred = pyqtSignal(str)
    step_title_changed = pyqtSignal(str)
    canceled = pyqtSignal()
    progress_changed = pyqtSignal(float)
    tasks_completed = pyqtSignal(bool)

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
        QgsMessageLog.logMessage(self.tr("{} was canceled").format(self.name), MESSAGE_CATEGORY, Qgis.Info)
        self.canceled = True
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
            QgsMessageLog.logMessage(f"{self.name} completed successfully", MESSAGE_CATEGORY, Qgis.Success)
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
                    Qgis.Warning,
                )
            else:
                message = f"{self.name} Exception:"
                for exception in self.exceptions:
                    message += f"\n{exception}"
                QgsMessageLog.logMessage(message, MESSAGE_CATEGORY, Qgis.Critical)
                raise Exception(message)

    def set_total_steps(self, total_steps: int):
        self.total_steps = total_steps

    def next_steps(self, step_title: str = None):
        self.step_title_changed.emit(step_title)
        self.current_step += 1
        self.progress_changed.emit(self.current_step / self.total_steps * 100)

    def add_exception(self, exception: Exception):
        self.exceptions.append(exception)

    def error_occur(self, message: str, category: str = MESSAGE_CATEGORY):
        QgsMessageLog.logMessage(message, category, Qgis.Critical)
        self.error_occurred.emit(message)
