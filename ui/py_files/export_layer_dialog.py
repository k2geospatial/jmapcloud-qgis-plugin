from qgis.core import QgsMapLayer, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.utils import iface

from ...core.constant import ElementTypeWrapper
from ...core.plugin_util import get_user_locale
from ...core.services.jmap_services_access import JMapMCS
from ...core.services.request_manager import RequestManager
from ...core.views import ExportSelectedLayerData, ProjectData
from .export_layer_dialog_base_ui import Ui_Dialog


class ExportLayerDialog(QtWidgets.QDialog, Ui_Dialog):
    selected_project = pyqtSignal(object)  # emits selected project
    layer_export_mode_changed = pyqtSignal(object)  # emits ExportMode

    # emits selected layer id to replace when in replace mode paylaod contains
    # { "id": str, "spatialDataSourceId": str }
    selected_layer_id_to_replace = pyqtSignal(dict)

    def __init__(self, jmap_mcs: JMapMCS):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.jmap_mcs = jmap_mcs
        self._selected_layer_id = None
        self._selected_layer_name = None
        self._selected_layer_type = None
        self.reset_dialog_state()

    def reset_dialog_state(self):
        self.error_label.clear()
        self.export_layer_pushButton.setEnabled(False)
        self.layer_replace_label.setEnabled(False)
        self.target_layer_replace_combo_box.clear()
        self.target_layer_replace_combo_box.setEnabled(False)

        # Uncheck both radio buttons even though they are auto-exclusive.
        self.create_layer_radio_button.setAutoExclusive(False)
        self.repalce_layer_radio_button.setAutoExclusive(False)
        self.create_layer_radio_button.setChecked(False)
        self.repalce_layer_radio_button.setChecked(False)
        self.create_layer_radio_button.setAutoExclusive(True)
        self.repalce_layer_radio_button.setAutoExclusive(True)

        self.create_layer_radio_button.setEnabled(False)
        self.repalce_layer_radio_button.setEnabled(False)

    def get_selected_layer_to_export(self) -> ExportSelectedLayerData:
        """
        Get the data of the selected layer to export,
        the target project and layer (if in replace mode)
        """
        return ExportSelectedLayerData(
            source_layer_id=self._selected_layer_id,
            JMC_project=self.JMap_project_combo_box.currentData(),
            mode=(
                ExportSelectedLayerData.ExportMode.replace
                if self.repalce_layer_radio_button.isChecked()
                else ExportSelectedLayerData.ExportMode.create
            ),
            target_JMC_layer_id=(
                self.target_layer_replace_combo_box.currentData()["id"]
                if self.repalce_layer_radio_button.isChecked()
                and self.target_layer_replace_combo_box.currentData()
                else None
            ),
            target_JMC_data_source_id=(
                self.target_layer_replace_combo_box.currentData()["spatialDataSourceId"]
                if self.repalce_layer_radio_button.isChecked()
                and self.target_layer_replace_combo_box.currentData()
                else None
            ),
        )

    def _on_project_selected(self, index):
        project_data: ProjectData = self.JMap_project_combo_box.itemData(index)
        if project_data:
            self.error_label.clear()
            if self.repalce_layer_radio_button.isChecked():
                self._load_project_layers(
                    project_data.project_id, self._selected_layer_type
                )
            else:
                self.target_layer_replace_combo_box.setEnabled(False)
                self.target_layer_replace_combo_box.clear()
                self.layer_replace_label.setEnabled(False)

            self.selected_project.emit(project_data)

    def _load_project_layers(self, project_id: str, elementType: str):
        def next_func(reply: RequestManager.ResponseData):
            # Ignore stale replies when user changed mode/project
            # while request was in-flight.
            if (
                not self.repalce_layer_radio_button.isChecked()
                or not self.JMap_project_combo_box.currentData()
                or self.JMap_project_combo_box.currentData().project_id != project_id
            ):
                self.target_layer_replace_combo_box.setEnabled(False)
                self.layer_replace_label.setEnabled(False)
                self.target_layer_replace_combo_box.clear()
                return

            if reply.status != QNetworkReply.NetworkError.NoError:
                self.error_label.setText(self.tr("Error loading project layers"))
                self.target_layer_replace_combo_box.setEnabled(False)
                self.layer_replace_label.setEnabled(False)
                self.target_layer_replace_combo_box.clear()
                return

            layers = reply.content or []

            if not layers:
                self.error_label.setText(
                    self.tr("No layers found in the selected project")
                )
                self.target_layer_replace_combo_box.setEnabled(False)
                self.layer_replace_label.setEnabled(False)
                return

            self.target_layer_replace_combo_box.clear()
            self.error_label.clear()

            locale: str = get_user_locale()

            layers = sorted(
                map(
                    lambda layer: {
                        "id": layer["id"],
                        "spatialDataSourceId": layer["spatialDataSourceId"],
                        "name": (
                            layer["name"][locale]
                            if locale in layer["name"]
                            else next(iter(layer["name"].values()))
                        ),
                    },
                    layers,
                ),
                key=lambda layer: layer["name"].lower(),
            )

            for layer in layers:
                self.target_layer_replace_combo_box.addItem(
                    layer["name"],
                    {
                        "id": layer["id"],
                        "spatialDataSourceId": layer["spatialDataSourceId"],
                    },
                )

            self.layer_replace_label.setEnabled(True)
            self.target_layer_replace_combo_box.setEnabled(True)
            self.export_layer_pushButton.setEnabled(True)

        self.jmap_mcs.get_project_layers_async(project_id, elementType).connect(
            next_func
        )

    def _on_mode_toggled(self, mode: ExportSelectedLayerData.ExportMode, checked: bool):
        if not checked:
            return

        self.layer_replace_label.setEnabled(
            mode == ExportSelectedLayerData.ExportMode.replace
        )
        self.export_layer_pushButton.setEnabled(
            mode == ExportSelectedLayerData.ExportMode.create
        )

        if (
            mode == ExportSelectedLayerData.ExportMode.replace
            and self.JMap_project_combo_box.currentData()
        ):
            project_id = self.JMap_project_combo_box.currentData().project_id
            self._load_project_layers(project_id, self._selected_layer_type)
        else:
            self.error_label.clear()
            self.layer_replace_label.setEnabled(False)
            self.target_layer_replace_combo_box.setEnabled(False)
            self.target_layer_replace_combo_box.clear()

        self.layer_export_mode_changed.emit(mode)

    def _on_layer_to_replace_selected(self, index):
        if index < 0:
            return

        payload = self.target_layer_replace_combo_box.itemData(index)
        if payload:
            self.selected_layer_id_to_replace.emit(payload)

    def set_selected_layer(self, layer: QgsMapLayer):
        if not layer:
            self._selected_layer_id = None
            self._selected_layer_name = None
            self._selected_layer_type = None
            return

        self._selected_layer_id = layer.id()
        self._selected_layer_name = layer.name()

        if isinstance(layer, QgsVectorLayer):
            self._selected_layer_type = layer.geometryType().name.lower()
        elif isinstance(layer, QgsRasterLayer):
            self._selected_layer_type = ElementTypeWrapper.IMAGE.name.lower()
        else:
            self.error_label.setText(self.tr("Unsupported layer type"))
            self._selected_layer_type = None
            self.export_layer_pushButton.setEnabled(False)
            return

        self.error_label.clear()

    def load_JMC_projects(self) -> bool:
        self.reset_dialog_state()
        self.JMap_project_combo_box.clear()
        self.JMap_project_combo_box.addItem(self.tr("Loading..."), None)
        self.JMap_project_combo_box.setEnabled(False)

        def _project_display_name(project: dict) -> str:
            name = project.get("name", "Unnamed project")
            if isinstance(name, dict):
                return next(iter(name.values()), "Unnamed project")
            return str(name)

        def next_func(reply: RequestManager.ResponseData):
            if reply.status != QNetworkReply.NetworkError.NoError:
                self.JMap_project_combo_box.clear()
                self.error_label.setText(self.tr("Error loading projects"))
                self.JMap_project_combo_box.setEnabled(False)
                self.export_layer_pushButton.setEnabled(False)
                return

            projects = reply.content or []

            if not projects:
                self.JMap_project_combo_box.clear()
                self.error_label.setText(self.tr("No projects found"))
                self.JMap_project_combo_box.setEnabled(False)
                self.export_layer_pushButton.setEnabled(False)
                return

            self.JMap_project_combo_box.clear()

            for project in sorted(
                projects, key=lambda p: _project_display_name(p).lower()
            ):
                project_data = ProjectData(
                    project_id=project["id"],
                    name=project["name"],
                    description=project["description"],
                    default_language=project["defaultLanguage"],
                )

                self.JMap_project_combo_box.addItem(
                    _project_display_name(project), project_data
                )

            try:
                self.JMap_project_combo_box.currentIndexChanged.disconnect(
                    self._on_project_selected
                )
            except TypeError:
                pass
            self.JMap_project_combo_box.currentIndexChanged.connect(
                self._on_project_selected
            )
            self.JMap_project_combo_box.setEnabled(True)

            self.create_layer_radio_button.setEnabled(True)
            try:
                self.create_layer_radio_button.toggled.disconnect()
            except TypeError:
                pass
            self.create_layer_radio_button.toggled.connect(
                lambda checked: self._on_mode_toggled(
                    ExportSelectedLayerData.ExportMode.create, checked
                )
            )
            self.repalce_layer_radio_button.setEnabled(True)
            try:
                self.repalce_layer_radio_button.toggled.disconnect()
            except TypeError:
                pass
            self.repalce_layer_radio_button.toggled.connect(
                lambda checked: self._on_mode_toggled(
                    ExportSelectedLayerData.ExportMode.replace, checked
                )
            )

            self.error_label.clear()

        return self.jmap_mcs.get_projects_async().connect(next_func)
