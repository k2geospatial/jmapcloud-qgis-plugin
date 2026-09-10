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

from ...ui.py_files.action_dialog import ActionDialog
from ..tasks.create_jmc_project_task import CreateJMCProjectTask
from ..tasks.export_layer_style_task import ExportLayersStyleTask
from ..tasks.step_guard import (
    ANALYZED_STEP_INACTIVITY_TIMEOUT_MS,
    STEP_INACTIVITY_TIMEOUT_MS,
    StepGuard,
)
from ..tasks.write_layer_tasks import ConvertLayersToZipTask
from ..views import LayerData, LayerFile, ProjectData
from .export_report import ExportReport
from .files_manager import DatasourceManager, FilesUploadManager
from .jmap_services_access import JMapMCS
from .request_manager import RequestManager

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
        self.report = ExportReport()
        self._cancel = False
        self._step_guard: StepGuard = None

    def export_project(self, project_data: ProjectData):
        if not self.exporting_project:
            self._cancel = False
            self.exporting_project = True
            self.project_data = project_data
            self.report.register_layers([layer.name() for layer in project_data.layers])
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
            self._abort(self.tr("The project does not contain any layer to export."))
            return
        self.action_dialog.set_text(self.tr("Converting layers to zip"))
        self.dir = tempfile.TemporaryDirectory()
        convert_layer_to_zip_task = ConvertLayersToZipTask(self.dir.name, self.project_data.layers)
        convert_layer_to_zip_task.progress_changed.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )

        def next_step(layers_data, layer_files):
            self._upload_layer_files(
                self._error_handler(layers_data, self.tr("convert layer to zip")), layer_files
            )

        guard = self._guard_step(self.tr("Converting layers to zip"), next_step)
        convert_layer_to_zip_task.progress_changed.connect(guard.touch)
        convert_layer_to_zip_task.tasks_completed.connect(guard.success)
        convert_layer_to_zip_task.run_failed.connect(guard.failure)

        convert_layer_to_zip_task.error_occurred.connect(self.report.note)
        self.feedback.canceled.connect(convert_layer_to_zip_task.cancel)
        convert_layer_to_zip_task.start()

    def _upload_layer_files(self, layers_data: list[LayerData], layer_files: list[LayerFile]):
        if self._cancel:
            return

        if len(layers_data) == 0:
            self._abort(self.tr("No layer could be prepared for upload."))
            return
        self.current_step += 1
        self.action_dialog.set_text(self.tr("Uploading layers files"))
        files_upload_manager = FilesUploadManager(
            self._request_manager, layers_data, layer_files, self.project_data.organization_id
        )

        def next_step(layers_data):
            self._create_datasource(self._error_handler(layers_data, self.tr("Upload layer files")))

        guard = self._guard_step(
            self.tr("Uploading layers files"), next_step, ANALYZED_STEP_INACTIVITY_TIMEOUT_MS
        )
        files_upload_manager.progress_changed.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        files_upload_manager.progress_changed.connect(guard.touch)
        files_upload_manager.step_title_changed.connect(self.action_dialog.set_text)
        files_upload_manager.error_occurred.connect(self.report.note)
        files_upload_manager.tasks_completed.connect(guard.success)
        files_upload_manager.run_failed.connect(guard.failure)
        self.feedback.canceled.connect(files_upload_manager.cancel)
        files_upload_manager.start()

    def _create_datasource(self, layers_data: list[LayerData]):
        if self._cancel:
            return
        self._cleanup_temp_dir()
        if len(layers_data) == 0:
            self._abort(self.tr("No layer file could be uploaded to JMap Cloud."))
            return

        self.current_step += 1
        self.action_dialog.set_text(self.tr("Creating datasources"))

        datasource_manager = DatasourceManager(
            self._request_manager, layers_data, self.project_data.organization_id
        )

        def next_step(layers_data):
            self._create_jmc_project(self._error_handler(layers_data, self.tr("Create datasource")))

        guard = self._guard_step(
            self.tr("Creating datasources"), next_step, ANALYZED_STEP_INACTIVITY_TIMEOUT_MS
        )
        datasource_manager.tasks_completed.connect(guard.success)
        datasource_manager.run_failed.connect(guard.failure)
        datasource_manager.progress_changed.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        datasource_manager.progress_changed.connect(guard.touch)
        datasource_manager.error_occurred.connect(self.report.note)
        datasource_manager.step_title_changed.connect(self.action_dialog.set_text)
        self.feedback.canceled.connect(datasource_manager.cancel)

        datasource_manager.start()

    def _create_jmc_project(self, layers_data: list[LayerData]):
        if self._cancel:
            return
        if len(layers_data) == 0:
            self._abort(self.tr("No datasource could be created in JMap Cloud."))
            return

        self.current_step += 1
        self.action_dialog.set_text(self.tr("Creating JMap Cloud project"))

        create_project_task = CreateJMCProjectTask(
            self._request_manager, self._jmap_mcs, layers_data, self.project_data
        )

        def next_step(layers_data):
            self._export_style(
                self._error_handler(layers_data, self.tr("Create JMap Cloud project"))
            )

        guard = self._guard_step(self.tr("Creating JMap Cloud project"), next_step)
        create_project_task.project_creation_finished.connect(guard.success)
        create_project_task.error_occurred.connect(self.report.note)
        create_project_task.taskTerminated.connect(
            lambda: guard.failure(self.tr("The JMap Cloud project could not be created."))
        )
        create_project_task.progressChanged.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        create_project_task.progressChanged.connect(guard.touch)
        self.feedback.canceled.connect(create_project_task.cancel)
        self.task_manager.addTask(create_project_task)

    def _export_style(self, layers_data: list[LayerData]):
        if self._cancel:
            return
        if len(layers_data) == 0:
            self._abort(self.tr("No layer could be added to the JMap Cloud project."))
            return

        self.current_step += 1
        self.action_dialog.set_text(self.tr("Exporting layer styles"))

        export_layer_styles_task = ExportLayersStyleTask(
            self._request_manager, layers_data, self.project_data
        )
        for layer_data in layers_data:
            self.report.exported(layer_data.layer_name)

        guard = self._guard_step(self.tr("Exporting layer styles"), self._finish)
        export_layer_styles_task.layer_styles_exportation_finished.connect(guard.success)
        export_layer_styles_task.layer_style_issue.connect(self.report.partially_exported)
        export_layer_styles_task.error_occurred.connect(self.report.note)
        export_layer_styles_task.taskTerminated.connect(
            lambda: guard.failure(self.tr("The layer styles could not be exported."))
        )
        export_layer_styles_task.progressChanged.connect(
            lambda value, current_step=self.current_step: self._set_progress(value, current_step)
        )
        export_layer_styles_task.progressChanged.connect(guard.touch)
        self.feedback.canceled.connect(export_layer_styles_task.cancel)
        self.task_manager.addTask(export_layer_styles_task)

    def _guard_step(
        self,
        step_name: str,
        on_success: callable,
        inactivity_timeout_ms: int = STEP_INACTIVITY_TIMEOUT_MS,
    ) -> StepGuard:
        self._step_guard = StepGuard(step_name, on_success, self._abort, inactivity_timeout_ms)
        return self._step_guard

    def _abort(self, message: str):
        """Stop the export and report `message` to the user in the action dialog."""
        if self._cancel or not self.exporting_project:
            return
        QgsMessageLog.logMessage(message, MESSAGE_CATEGORY, Qgis.MessageLevel.Critical)
        self.report.aborted = True
        self.report.note(message)
        self._finish(False)

    def _error_handler(self, layers_data: list[LayerData], step_string: str) -> list[LayerData]:
        success: list[LayerData] = []
        file_error: list[LayerData] = []
        other_error: list[LayerData] = []
        message = ""
        for layer_data in layers_data:
            if layer_data.status != LayerData.Status.no_error:
                reason = layer_data.status_reason or layer_data.status.value
                self.report.skipped(layer_data.layer_name, reason)
                new_message = self.tr("Layer '{}' was skipped during '{}': {}").format(
                    layer_data.layer_name, step_string, reason
                )
                message += new_message
                other_error.append(layer_data)
            elif (
                layer_data.layer_file is not None
                and layer_data.layer_file.upload_status != LayerFile.Status.no_error
            ):
                reason = layer_data.status_reason or self.tr(
                    "its file {} could not be uploaded ({})"
                ).format(
                    layer_data.layer_file.file_name,
                    layer_data.layer_file.upload_status.value,
                )
                self.report.skipped(layer_data.layer_name, reason)
                new_message = self.tr("Layer '{}' was skipped during '{}': {}\n").format(
                    layer_data.layer_name, step_string, reason
                )
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
        if not self.exporting_project:
            return
        self.exporting_project = False
        self._release_step_guard()
        self._cleanup_temp_dir()

        self.report.aborted = not success
        self.report.project_name = self.project_data.name
        self.report.project_id = self.project_data.project_id
        self.action_dialog.action_finished(self.report.to_html(), error=not success)
        self.project_exportation_finished.emit(success)
        self.action_dialog = ActionDialog()
        self.feedback = self.action_dialog.feedback()
        self.current_step = 0
        self.report = ExportReport()

    def _cleanup_temp_dir(self):
        if self.dir is None:
            return
        try:
            self.dir.cleanup()
        except Exception as exception:
            QgsMessageLog.logMessage(
                self.tr("Could not remove the temporary directory: {}").format(exception),
                MESSAGE_CATEGORY,
                Qgis.MessageLevel.Warning,
            )
        self.dir = None

    def _release_step_guard(self):
        if self._step_guard is not None:
            self._step_guard.abandon()
            self._step_guard = None

    def is_exporting_project(self) -> bool:
        return self.exporting_project

    def cancel(self):
        self._cancel = True
        self.exporting_project = False
        self._release_step_guard()
        self._cleanup_temp_dir()
        self.action_dialog = ActionDialog()
        self.feedback = self.action_dialog.feedback()
        self.current_step = 0
        self.report = ExportReport()
