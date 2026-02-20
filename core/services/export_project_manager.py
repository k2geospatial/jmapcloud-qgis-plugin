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
import tempfile

from qgis.core import Qgis, QgsApplication, QgsMessageLog
from qgis.PyQt.QtCore import QObject, pyqtSignal

from .jmap_services_access import JMapMCS
from .request_manager import RequestManager

from .files_manager import DatasourceManager, FilesUploadManager
from ..tasks.create_jmc_project_task import CreateJMCProjectTask
from ..tasks.export_layer_style_task import ExportLayersStyleTask
from ..tasks.write_layer_tasks import ConvertLayersToZipTask
from ..views import LayerData, LayerFile, ProjectData
from ...ui.py_files.action_dialog import ActionDialog

MESSAGE_CATEGORY = "ExportProjectTask"
TOTAL_STEPS = 5


class ExportProjectManager(QObject):
    project_exportation_finished = pyqtSignal(bool)

    def __init__(self, request_manager: RequestManager, jmap_mcs: JMapMCS):
        super().__init__()
        self._request_manager = request_manager
        self._jmap_mcs = jmap_mcs
        self.dir = None
        self.task_manager = QgsApplication.taskManager()
        self.exporting_project = False
        self.action_dialog = ActionDialog()
        self.feedback = self.action_dialog.feedback()
        self.current_step = 0
        self.errors: list[str] = []
        self._cancel = False

    def export_project(self, project_data: ProjectData):
        if not self.exporting_project:
            self._cancel = False
            self.exporting_project = True
            self.project_data = project_data
            self.action_dialog.show_dialog()
            self.action_dialog.progressBar.setFormat("%p%")
            self.action_dialog.progress_info_label.setText(self.tr("Initializing loading"))
            self.action_dialog.set_cancelable_mode(self.tr("<h3>Project exportation canceled</h3>"))
            self.feedback.canceled.connect(self.cancel)
            self._convert_layer_to_zip()
        else:
            self.action_dialog.show()

    def _convert_layer_to_zip(self):
        if self._cancel:
            return
        if len(self.project_data.layers) == 0:
            self._finish(False)
            return
        self.action_dialog.set_text(self.tr("Converting layers to zip"))
        self.dir = tempfile.TemporaryDirectory()
        convert_layer_to_zip_task = ConvertLayersToZipTask(self.dir.name, self.project_data.layers)
        convert_layer_to_zip_task.progress_changed.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        def next_step(layers_data, layer_files):
            self._upload_layer_files(self._error_handler(layers_data, self.tr("convert layer to zip")), layer_files)

        convert_layer_to_zip_task.tasks_completed.connect(next_step)

        convert_layer_to_zip_task.error_occurred.connect(self.errors.append)
        self.feedback.canceled.connect(convert_layer_to_zip_task.cancel)
        convert_layer_to_zip_task.start()

    def _upload_layer_files(self, layers_data: list[LayerData], layer_files: list[LayerFile]):
        if self._cancel:
            return

        if len(layers_data) == 0:
            self._finish(False)
            return
        self.current_step += 1
        self.action_dialog.set_text(self.tr("Uploading layers files"))
        files_upload_manager = FilesUploadManager(self._request_manager, layers_data, layer_files, self.project_data.organization_id)
        next_step = lambda layers_data: self._create_datasource(
            self._error_handler(layers_data, self.tr("Upload layer files"))
        )
        files_upload_manager.progress_changed.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        files_upload_manager.step_title_changed.connect(self.action_dialog.set_text)
        files_upload_manager.error_occurred.connect(self.errors.append)
        files_upload_manager.tasks_completed.connect(next_step)
        self.feedback.canceled.connect(files_upload_manager.cancel)
        files_upload_manager.run()

    def _create_datasource(self, layers_data: list[LayerData]):
        if self._cancel:
            return
        self.dir.cleanup()
        if len(layers_data) == 0:
            self._finish(False)
            return

        self.current_step += 1
        self.action_dialog.set_text(self.tr("Creating datasources"))

        datasource_manager = DatasourceManager(self._request_manager, layers_data, self.project_data.organization_id)
        next_step = lambda layers_data: self._create_jmc_project(
            self._error_handler(layers_data, self.tr("Create datasource"))
        )
        datasource_manager.tasks_completed.connect(next_step)
        datasource_manager.progress_changed.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        datasource_manager.error_occurred.connect(self.errors.append)
        datasource_manager.step_title_changed.connect(self.action_dialog.set_text)
        self.feedback.canceled.connect(datasource_manager.cancel)

        datasource_manager.run()

    def _create_jmc_project(self, layers_data: list[LayerData]):
        if self._cancel:
            return
        if len(layers_data) == 0:
            self._finish(False)
            return

        self.current_step += 1
        self.action_dialog.set_text(self.tr("Creating JMap Cloud project"))

        create_project_task = CreateJMCProjectTask(self._request_manager, self._jmap_mcs, layers_data, self.project_data)
        next_step = lambda layers_data: self._export_style(
            self._error_handler(layers_data, self.tr("Create JMap Cloud project"))
        )
        create_project_task.project_creation_finished.connect(next_step)
        create_project_task.error_occurred.connect(self.errors.append)
        create_project_task.progressChanged.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        self.feedback.canceled.connect(create_project_task.cancel)
        self.task_manager.addTask(create_project_task)

    def _export_style(self, layers_data: list[LayerData]):
        if self._cancel:
            return
        if len(layers_data) == 0:
            self._finish(False)
            return

        self.current_step += 1
        self.action_dialog.set_text(self.tr("Exporting layer styles"))

        export_layer_styles_task = ExportLayersStyleTask(self._request_manager, layers_data, self.project_data)
        export_layer_styles_task.layer_styles_exportation_finished.connect(self._finish)
        export_layer_styles_task.error_occurred.connect(self.errors.append)
        export_layer_styles_task.progressChanged.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        self.feedback.canceled.connect(export_layer_styles_task.cancel)
        self.task_manager.addTask(export_layer_styles_task)

    def _error_handler(self, layers_data: list[LayerData], step_string: str) -> list[LayerData]:
        success: list[LayerData] = []
        file_error: list[LayerData] = []
        other_error: list[LayerData] = []
        message = ""
        for layer_data in layers_data:
            if layer_data.status != LayerData.Status.no_error:
                new_message = self.tr("{} in task {} for layer {}").format(
                    layer_data.status, step_string, layer_data.layer_name
                )
                self.errors.append(new_message)
                message += new_message
                other_error.append(layer_data)
            elif layer_data.layer_file != None and layer_data.layer_file.upload_status != LayerFile.Status.no_error:
                new_message = self.tr("{} in task {} for layer {} with file {}\n").format(
                    layer_data.layer_file.upload_status,
                    step_string,
                    layer_data.layer_name,
                    layer_data.layer_file.file_name,
                )
                self.errors.append(new_message)
                message += new_message
                file_error.append(layer_data)
            else:
                success.append(layer_data)
        if message != "":
            QgsMessageLog.logMessage(message, MESSAGE_CATEGORY, Qgis.MessageLevel.Critical)
        return success

    def _set_progress(self, value, current_step):
        total_progress = (current_step * 100 + value) / TOTAL_STEPS
        self.action_dialog.set_progress(total_progress)

    def _finish(self, success: bool = True):
        message = self.tr("<h3>Project exportation finished<3>")
        if len(self.errors) > 0:
            message += self.tr("<h4>Some errors occurred during the process:</h4>")
            for error in self.errors:
                message += "<p>{}</p>".format(error.replace("\n", "<br>"))
        self.action_dialog.action_finished(message)
        self.project_exportation_finished.emit(success)
        self.exporting_project = False
        self.action_dialog = ActionDialog()
        self.feedback = self.action_dialog.feedback()
        self.current_step = 0
        self.errors = []

    def is_exporting_project(self) -> bool:
        return self.exporting_project

    def cancel(self):
        self._cancel = True
        self.exporting_project = False
        self.action_dialog = ActionDialog()
        self.feedback = self.action_dialog.feedback()
        self.current_step = 0
        self.errors = []
