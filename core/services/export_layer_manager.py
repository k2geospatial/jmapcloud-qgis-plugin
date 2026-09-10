from tempfile import TemporaryDirectory
from typing import Union

from qgis.core import Qgis, QgsApplication, QgsFeedback, QgsMessageLog, QgsProject
from qgis.PyQt.QtCore import QObject, pyqtSignal

from ...ui.py_files.action_dialog import ActionDialog
from ..tasks.create_layer_task import CreateLayerTask
from ..tasks.export_layer_style_task import ExportLayerStyleTask
from ..tasks.load_jmc_datasource_references_task import LoadJMCDataSourceReferencesTask
from ..tasks.remove_layer_style_task import RemoveLayerStyleTask
from ..tasks.replace_layer_task import ReplaceLayerTask
from ..tasks.step_guard import (
    ANALYZED_STEP_INACTIVITY_TIMEOUT_MS,
    STEP_INACTIVITY_TIMEOUT_MS,
    StepGuard,
)
from ..tasks.write_layer_tasks import ConvertLayerToZipTask
from ..views import ExportSelectedLayerData, LayerData, LayerFile
from .export_report import ExportReport
from .files_manager import DatasourceManager, FilesUploadManager
from .jmap_services_access import JMapMCS
from .request_manager import RequestManager

MESSAGE_CATEGORY = "ExportLayerTask"
TOTAL_STEPS = 5


class ExportLayerManager(QObject):
    # Emits the list of project references that are referencing the datasource,
    # each reference contains the project name and
    # the list of layer names referencing the datasource
    data_source_references_loaded = pyqtSignal(list)
    layer_exportation_finished = pyqtSignal(bool)

    def __init__(self, request_manager: RequestManager, jmap_mcs: JMapMCS):
        super().__init__()
        self._request_manager = request_manager
        self._jmap_mcs = jmap_mcs
        self._dir: TemporaryDirectory = None
        self._task_manager = QgsApplication.taskManager()
        self._exporting_layer: bool = False
        self._action_dialog: ActionDialog = ActionDialog()
        self._feedback: QgsFeedback = self._action_dialog.feedback()
        self._current_step: int = 0
        self.report = ExportReport(ExportReport.Scope.layer)
        self._is_canceled: bool = False
        self._step_guard: StepGuard = None

    def is_exporting_layer(self) -> bool:
        return self._exporting_layer

    def load_data_source_referenced_by_other_projects(self, data_source_id: str, project_id: str):
        task = LoadJMCDataSourceReferencesTask(self._jmap_mcs, data_source_id, project_id)

        def _on_data_source_references_loaded(references: list[dict[str, list[str]]]):
            self.data_source_references_loaded.emit(references)

        task.tasks_completed.connect(_on_data_source_references_loaded)
        task.error_occurred.connect(self.report.note)
        self._task_manager.addTask(task)

    def create_new_layer(
        self, organisation_id: str, export_selected_layer_data: ExportSelectedLayerData
    ):
        self._start_layer_exportation(organisation_id, export_selected_layer_data)

    def replace_layer(
        self, organisation_id: str, export_selected_layer_data: ExportSelectedLayerData
    ):
        self._start_layer_exportation(organisation_id, export_selected_layer_data)

    def _start_layer_exportation(
        self, organisation_id: str, export_selected_layer_data: ExportSelectedLayerData
    ):
        if self._exporting_layer:
            self._action_dialog.show_dialog()
            return

        self._is_canceled = False
        self._exporting_layer = True
        self._action_dialog.show_dialog()
        self._action_dialog.progressBar.setFormat("%p%")
        self._action_dialog.progress_info_label.setText(self.tr("Initializing loading"))
        self._action_dialog.set_cancelable_mode(self.tr("<h3>Layer exportation canceled</h3>"))
        self._feedback.canceled.connect(self._on_cancel)
        self._current_step = 0
        self.report = ExportReport(ExportReport.Scope.layer)
        layer = QgsProject.instance().mapLayer(export_selected_layer_data.source_layer_id)
        if layer:
            self.report.register_layers([layer.name()])

        self._convert_layer_to_zip(organisation_id, export_selected_layer_data)

    def _convert_layer_to_zip(
        self, organisation_id: str, export_selected_layer_data: ExportSelectedLayerData
    ):
        if self._is_canceled:
            return
        selected_layer = QgsProject.instance().mapLayer(export_selected_layer_data.source_layer_id)

        if not selected_layer:
            self._abort(self.tr("Layer not found"))
            return

        self._action_dialog.set_text(self.tr("Converting layer to zip"))
        self._dir = TemporaryDirectory()
        convert_layer_to_zip_task = ConvertLayerToZipTask(self._dir.name, selected_layer)
        convert_layer_to_zip_task.progress_changed.connect(
            lambda value, current_step=self._current_step: self._set_progress(value, current_step)
        )

        def next_step(layer_data, layer_file):
            if self._validate_layer_errors(layer_data, self.tr("convert layer to zip")) is None:
                self._finish(False)
                return

            if layer_file is None:
                if export_selected_layer_data.mode == ExportSelectedLayerData.ExportMode.create:
                    self._create_datasource(layer_data, organisation_id, export_selected_layer_data)
                else:
                    self._update_datasource(layer_data, organisation_id, export_selected_layer_data)
                return

            self._upload_layer_files(
                layer_data, layer_file, organisation_id, export_selected_layer_data
            )

        guard = self._guard_step(self.tr("Converting layer to zip"), next_step)
        convert_layer_to_zip_task.progress_changed.connect(guard.touch)
        convert_layer_to_zip_task.tasks_completed.connect(guard.success)
        convert_layer_to_zip_task.run_failed.connect(guard.failure)
        convert_layer_to_zip_task.error_occurred.connect(self.report.note)
        self._feedback.canceled.connect(convert_layer_to_zip_task.cancel)
        convert_layer_to_zip_task.start()

    def _upload_layer_files(
        self,
        layer_data: LayerData,
        layer_file: LayerFile,
        organisation_id: str,
        export_selected_layer_data: ExportSelectedLayerData,
    ):
        if self._is_canceled:
            return
        if layer_file is None:
            if export_selected_layer_data.mode == ExportSelectedLayerData.ExportMode.create:
                self._create_datasource(layer_data, organisation_id, export_selected_layer_data)
            else:
                self._update_datasource(layer_data, organisation_id, export_selected_layer_data)
            return

        self._current_step += 1
        self._action_dialog.set_text(self.tr("Uploading layer files"))

        files_upload_manager = FilesUploadManager(
            self._request_manager, [layer_data], [layer_file], organisation_id
        )

        def next_step(layers_data):
            layer_data_result = layers_data[0]

            if (
                self._validate_layer_errors(layer_data_result, self.tr("Upload layer files"))
                is None
            ):
                self._finish(False)
                return

            if export_selected_layer_data.mode == ExportSelectedLayerData.ExportMode.create:
                self._create_datasource(
                    layer_data_result, organisation_id, export_selected_layer_data
                )
            else:
                self._update_datasource(
                    layer_data_result, organisation_id, export_selected_layer_data
                )

        files_upload_manager.progress_changed.connect(
            lambda value, current_step=self._current_step: self._set_progress(value, current_step)
        )
        guard = self._guard_step(
            self.tr("Uploading layer files"), next_step, ANALYZED_STEP_INACTIVITY_TIMEOUT_MS
        )
        files_upload_manager.progress_changed.connect(guard.touch)
        files_upload_manager.step_title_changed.connect(self._action_dialog.set_text)
        files_upload_manager.error_occurred.connect(self.report.note)
        files_upload_manager.tasks_completed.connect(guard.success)
        files_upload_manager.run_failed.connect(guard.failure)
        self._feedback.canceled.connect(files_upload_manager.cancel)
        files_upload_manager.start()

    def _create_datasource(
        self,
        layer_data: LayerData,
        organisation_id: str,
        export_selected_layer_data: ExportSelectedLayerData,
    ):
        if self._is_canceled:
            return

        self._cleanup_temp_dir()

        self._current_step += 1
        self._action_dialog.set_text(self.tr("Creating datasource"))

        datasource_manager = DatasourceManager(
            self._request_manager, [layer_data], organisation_id, export_selected_layer_data.mode
        )

        def next_step(layers_data):
            layer_data_result = layers_data[0]
            if self._validate_layer_errors(layer_data_result, self.tr("Create datasource")) is None:
                self._finish(False)
                return

            self._add_layer_to_jmc_project(
                layer_data_result, organisation_id, export_selected_layer_data
            )

        datasource_manager.progress_changed.connect(
            lambda value, current_step=self._current_step: self._set_progress(value, current_step)
        )
        guard = self._guard_step(
            self.tr("Creating datasource"), next_step, ANALYZED_STEP_INACTIVITY_TIMEOUT_MS
        )
        datasource_manager.progress_changed.connect(guard.touch)
        datasource_manager.error_occurred.connect(self.report.note)
        datasource_manager.tasks_completed.connect(guard.success)
        datasource_manager.run_failed.connect(guard.failure)
        self._feedback.canceled.connect(datasource_manager.cancel)
        datasource_manager.start()

    def _update_datasource(
        self,
        layer_data: LayerData,
        organisation_id: str,
        export_selected_layer_data: ExportSelectedLayerData,
    ):
        if self._is_canceled:
            return

        layer_data.datasource_id = export_selected_layer_data.target_JMC_data_source_id
        self._cleanup_temp_dir()

        self._current_step += 1
        self._action_dialog.set_text(self.tr("Updating datasource"))

        datasource_manager = DatasourceManager(
            self._request_manager, [layer_data], organisation_id, export_selected_layer_data.mode
        )

        def next_step(layers_data):
            layer_data_result = layers_data[0]
            if self._validate_layer_errors(layer_data_result, self.tr("Update datasource")) is None:
                self._finish(False)
                return

            self._replace_layer_in_jmc_project(
                layer_data_result, organisation_id, export_selected_layer_data
            )

        datasource_manager.progress_changed.connect(
            lambda value, current_step=self._current_step: self._set_progress(value, current_step)
        )
        guard = self._guard_step(
            self.tr("Updating datasource"), next_step, ANALYZED_STEP_INACTIVITY_TIMEOUT_MS
        )
        datasource_manager.progress_changed.connect(guard.touch)
        datasource_manager.error_occurred.connect(self.report.note)
        datasource_manager.tasks_completed.connect(guard.success)
        datasource_manager.run_failed.connect(guard.failure)
        self._feedback.canceled.connect(datasource_manager.cancel)
        datasource_manager.start()

    def _add_layer_to_jmc_project(
        self,
        layer_data: LayerData,
        organisation_id: str,
        export_selected_layer_data: ExportSelectedLayerData,
    ):
        if self._is_canceled:
            return

        self._current_step += 1
        self._action_dialog.set_text(self.tr("Adding layer to project"))
        create_layer_task = CreateLayerTask(
            self._jmap_mcs, organisation_id, layer_data, export_selected_layer_data.JMC_project
        )

        def next_step(layer_data):
            if self._validate_layer_errors(layer_data, self.tr("Create layer in JMC")) is None:
                self._finish(False)
                return

            self._export_style(layer_data, export_selected_layer_data)

        guard = self._guard_step(self.tr("Adding layer to project"), next_step)
        create_layer_task.layer_creation_finished.connect(guard.success)
        create_layer_task.error_occurred.connect(self.report.note)
        create_layer_task.progressChanged.connect(
            lambda value, current_step=self._current_step: self._set_progress(value, current_step)
        )

        if create_layer_task.run() is False:
            guard.failure(self.tr("The layer could not be added to the JMap Cloud project."))

    def _replace_layer_in_jmc_project(
        self,
        layer_data: LayerData,
        organisation_id: str,
        export_selected_layer_data: ExportSelectedLayerData,
    ):
        if self._is_canceled:
            return

        self._current_step += 1
        self._action_dialog.set_text(self.tr("Replacing layer in project"))

        # replace layer task
        replace_layer_task = ReplaceLayerTask(
            self._jmap_mcs, organisation_id, layer_data, export_selected_layer_data
        )

        def next_step(layer_data):
            if self._validate_layer_errors(layer_data, self.tr("Replace layer in JMC")) is None:
                self._finish(False)
                return

            layer_data.jmc_layer_id = export_selected_layer_data.target_JMC_layer_id
            self._export_style(
                layer_data, export_selected_layer_data, should_remove_old_styles=True
            )

        guard = self._guard_step(self.tr("Replacing layer in project"), next_step)
        replace_layer_task.layer_replacement_finished.connect(guard.success)
        replace_layer_task.error_occurred.connect(self.report.note)
        replace_layer_task.progressChanged.connect(
            lambda value, current_step=self._current_step: self._set_progress(value, current_step)
        )
        if replace_layer_task.run() is False:
            guard.failure(self.tr("The layer could not be replaced in the JMap Cloud project."))

    def _export_style(
        self,
        layer_data: LayerData,
        export_selected_layer_data: ExportSelectedLayerData,
        should_remove_old_styles: bool = False,
    ):
        if self._is_canceled:
            return

        self._current_step += 1
        self._action_dialog.set_text(self.tr("Exporting layer style"))
        self.report.exported(layer_data.layer_name)
        export_layer_style_task = ExportLayerStyleTask(
            self._request_manager,
            layer_data,
            export_selected_layer_data.JMC_project,
        )
        export_layer_style_task.error_occurred.connect(self.report.note)
        export_layer_style_task.progressChanged.connect(
            lambda value, current_step=self._current_step: self._set_progress(value, current_step)
        )

        def next_step(_style_rule_id):
            if layer_data.layer_type == LayerData.LayerType.file_raster:
                self._finish()
            elif should_remove_old_styles and _style_rule_id is not None:
                self._remove_layer_styles(layer_data, export_selected_layer_data, _style_rule_id)
            else:
                self._finish()

        guard = self._guard_step(self.tr("Exporting layer style"), next_step)
        export_layer_style_task.export_layer_style_completed.connect(guard.success)
        export_layer_style_task.layer_style_issue.connect(self.report.partially_exported)

        self._feedback.canceled.connect(export_layer_style_task.cancel)
        if export_layer_style_task.run() is False:
            guard.failure(self.tr("The layer style could not be exported."))

    def _remove_layer_styles(
        self,
        layer_data: LayerData,
        export_selected_layer_data: ExportSelectedLayerData,
        new_style_rule_id: str,
    ):
        if self._is_canceled:
            return

        self._action_dialog.set_text(self.tr("Removing layer styles"))
        remove_layer_style_task = RemoveLayerStyleTask(
            self._jmap_mcs, layer_data, export_selected_layer_data.JMC_project, new_style_rule_id
        )
        remove_layer_style_task.error_occurred.connect(self.report.note)

        guard = self._guard_step(self.tr("Removing layer styles"), self._finish)
        remove_layer_style_task.remove_layer_style_task_completed.connect(guard.success)

        self._feedback.canceled.connect(remove_layer_style_task.cancel)
        if remove_layer_style_task.run() is False:
            guard.failure(self.tr("The previous layer styles could not be removed."))

    def _validate_layer_errors(
        self, layer_data: Union[LayerData, None], step_string: str
    ) -> Union[LayerData, None]:
        """
        Validate a single layer for the current step and aggregate/log errors.
        """
        if layer_data is None:
            return None

        if layer_data.status != LayerData.Status.no_error:
            reason = layer_data.status_reason or layer_data.status.value
            self.report.skipped(layer_data.layer_name, reason)
            QgsMessageLog.logMessage(
                "Layer '{}' was skipped during '{}': {}".format(
                    layer_data.layer_name, step_string, reason
                ),
                MESSAGE_CATEGORY,
                Qgis.MessageLevel.Critical,
            )
            return None

        if (
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
            QgsMessageLog.logMessage(
                "Layer '{}' was skipped during '{}': {}".format(
                    layer_data.layer_name, step_string, reason
                ),
                MESSAGE_CATEGORY,
                Qgis.MessageLevel.Critical,
            )
            return None

        return layer_data

    def _set_progress(self, value, current_step):
        total_progress = (current_step * 100 + value) / TOTAL_STEPS
        self._action_dialog.set_progress(total_progress)

    def _guard_step(
        self,
        step_name: str,
        on_success: callable,
        inactivity_timeout_ms: int = STEP_INACTIVITY_TIMEOUT_MS,
    ) -> StepGuard:
        self._step_guard = StepGuard(step_name, on_success, self._abort, inactivity_timeout_ms)
        return self._step_guard

    def _abort(self, message: str):
        """Stop the exportation and report `message` to the user in the action dialog."""
        if self._is_canceled or not self._exporting_layer:
            return
        QgsMessageLog.logMessage(message, MESSAGE_CATEGORY, Qgis.MessageLevel.Critical)
        self.report.note(message)
        self._finish(False)

    def _release_step_guard(self):
        if self._step_guard is not None:
            self._step_guard.abandon()
            self._step_guard = None

    def _cleanup_temp_dir(self):
        if self._dir is None:
            return
        try:
            self._cleanup_temp_dir()
        except Exception as exception:
            QgsMessageLog.logMessage(
                self.tr("Could not remove the temporary directory: {}").format(exception),
                MESSAGE_CATEGORY,
                Qgis.MessageLevel.Warning,
            )
        self._dir = None

    def _on_cancel(self):
        self._is_canceled = True
        self._exporting_layer = False
        self._release_step_guard()
        self._cleanup_temp_dir()
        self._action_dialog = ActionDialog()
        self._feedback = self._action_dialog.feedback()
        self._current_step = 0
        self.report = ExportReport(ExportReport.Scope.layer)

    def _finish(self, success: bool = True):
        if not self._exporting_layer:
            return
        self._exporting_layer = False
        self._release_step_guard()
        self._cleanup_temp_dir()

        self.report.aborted = not success
        self._action_dialog.action_finished(self.report.to_html(), error=not success)
        self.layer_exportation_finished.emit(success)
        self._action_dialog = ActionDialog()
        self._feedback = self._action_dialog.feedback()
        self._current_step = 0
        self.report = ExportReport(ExportReport.Scope.layer)
