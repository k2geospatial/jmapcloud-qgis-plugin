from qgis.core import QgsMapLayer, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt import QtWidgets
from qgis.PyQt.QtCore import QSortFilterProxyModel, Qt, pyqtSignal
from qgis.PyQt.QtGui import QStandardItem, QStandardItemModel
from qgis.PyQt.QtNetwork import QNetworkReply
from qgis.utils import iface

from ...core.constant import ElementTypeWrapper, Permission
from ...core.plugin_util import get_user_locale
from ...core.services.auth_manager import JMapAuth
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

    def __init__(self, jmap_mcs: JMapMCS, auth_manager: JMapAuth):
        super().__init__(iface.mainWindow())
        self.setupUi(self)
        self.jmap_mcs = jmap_mcs
        self.auth_manager = auth_manager
        self._selected_layer_id = None
        self._selected_layer_name = None
        self._selected_layer_type = None

        # Tree model + recursive filter proxy backing the "layer to replace" tree.
        self._layer_model = QStandardItemModel()
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._layer_model)
        self._proxy.setRecursiveFilteringEnabled(True)
        self._proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.target_layer_tree_view.setModel(self._proxy)
        self.target_layer_tree_view.setHeaderHidden(True)
        self.layer_filter_line_edit.textChanged.connect(self._on_filter_text_changed)
        self.target_layer_tree_view.selectionModel().selectionChanged.connect(
            self._on_tree_selection_changed
        )

        self.reset_dialog_state()

    def reset_dialog_state(self):
        self.error_label.clear()
        self.export_layer_pushButton.setEnabled(False)
        self.layer_replace_label.setEnabled(False)
        self._clear_layer_tree()

        # Uncheck both radio buttons even though they are auto-exclusive.
        self.create_layer_radio_button.setAutoExclusive(False)
        self.repalce_layer_radio_button.setAutoExclusive(False)
        self.create_layer_radio_button.setChecked(False)
        self.repalce_layer_radio_button.setChecked(False)
        self.create_layer_radio_button.setAutoExclusive(True)
        self.repalce_layer_radio_button.setAutoExclusive(True)

        self.create_layer_radio_button.setEnabled(False)
        self.repalce_layer_radio_button.setEnabled(False)

    def _clear_layer_tree(self):
        """Reset and disable the layer tree + filter box."""
        self._layer_model.clear()
        self.layer_filter_line_edit.clear()
        self.layer_filter_line_edit.setEnabled(False)
        self.target_layer_tree_view.setEnabled(False)

    def _resolve_name(self, name: dict, locale: str) -> str:
        """Resolve a locale-keyed name dict to a display string."""
        if not isinstance(name, dict) or not name:
            return str(name) if name else ""
        if locale in name:
            return name[locale]
        return next(iter(name.values()))

    def _selected_target_payload(self) -> dict:
        """Return {"id", "spatialDataSourceId"} of the selected layer, or None."""
        indexes = self.target_layer_tree_view.selectionModel().selectedIndexes()
        if not indexes:
            return None
        source_index = self._proxy.mapToSource(indexes[0])
        item = self._layer_model.itemFromIndex(source_index)
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def get_selected_layer_to_export(self) -> ExportSelectedLayerData:
        """
        Get the data of the selected layer to export,
        the target project and layer (if in replace mode)
        """
        is_replace = self.repalce_layer_radio_button.isChecked()
        payload = self._selected_target_payload() if is_replace else None
        return ExportSelectedLayerData(
            source_layer_id=self._selected_layer_id,
            JMC_project=self.JMap_project_combo_box.currentData(),
            mode=(
                ExportSelectedLayerData.ExportMode.replace
                if is_replace
                else ExportSelectedLayerData.ExportMode.create
            ),
            target_JMC_layer_id=payload["id"] if payload else None,
            target_JMC_data_source_id=payload["spatialDataSourceId"] if payload else None,
        )

    def _on_project_selected(self, index):
        project_data: ProjectData = self.JMap_project_combo_box.itemData(index)
        if project_data:
            self.error_label.clear()
            if self.repalce_layer_radio_button.isChecked():
                self._load_project_layers(project_data.project_id, self._selected_layer_type)
            else:
                self._clear_layer_tree()
                self.layer_replace_label.setEnabled(False)

            self.selected_project.emit(project_data)

    def _load_project_layers(self, project_id: str, elementType: str):
        def next_func(replies: dict):
            # Ignore stale replies when user changed mode/project
            # while request was in-flight.
            if (
                not self.repalce_layer_radio_button.isChecked()
                or not self.JMap_project_combo_box.currentData()
                or self.JMap_project_combo_box.currentData().project_id != project_id
            ):
                self.layer_replace_label.setEnabled(False)
                self._clear_layer_tree()
                return

            layers_reply = replies.get("layers")
            groups_reply = replies.get("layer-groups")

            if (
                layers_reply is None
                or groups_reply is None
                or layers_reply.status != QNetworkReply.NetworkError.NoError
                or groups_reply.status != QNetworkReply.NetworkError.NoError
            ):
                self.error_label.setText(self.tr("Error loading project layers"))
                self.layer_replace_label.setEnabled(False)
                self._clear_layer_tree()
                return

            layers = layers_reply.content or []

            if not layers:
                self.error_label.setText(self.tr("No layers found in the selected project"))
                self.layer_replace_label.setEnabled(False)
                self._clear_layer_tree()
                return

            locale: str = get_user_locale()
            spatialDataSourceIdByLayerId = {
                layer["id"]: layer["spatialDataSourceId"] for layer in layers
            }

            self._layer_model.clear()
            self.layer_filter_line_edit.clear()
            self.error_label.clear()

            self._populate_tree(
                groups_reply.content or [],
                spatialDataSourceIdByLayerId,
                locale,
                self._layer_model.invisibleRootItem(),
            )

            if self._layer_model.invisibleRootItem().rowCount() == 0:
                self.error_label.setText(self.tr("No layers found in the selected project"))
                self.layer_replace_label.setEnabled(False)
                self._clear_layer_tree()
                return

            self.target_layer_tree_view.expandAll()

            self.layer_replace_label.setEnabled(True)
            self.layer_filter_line_edit.setEnabled(True)
            self.target_layer_tree_view.setEnabled(True)
            # Export stays disabled until a valid layer is selected.
            self.export_layer_pushButton.setEnabled(False)

        signal = self.jmap_mcs.get_project_layers_and_groups_async(project_id, elementType)
        if signal is not None:
            signal.connect(next_func)

    def _populate_tree(
        self,
        nodes: list,
        spatialDataSourceIdByLayerId: dict,
        locale: str,
        parent_item: QStandardItem,
    ) -> bool:
        """
        Recursively build the layer/group tree under parent_item, preserving the
        JMap Cloud project's original layer/group ordering.

        Only LAYER nodes present in `spatialDataSourceIdByLayerId` (matching geometry
        type) are kept; GROUP nodes are kept only if they contain at least one kept
        descendant (empty groups are pruned). Returns True if anything was appended.
        """
        kept_any = False
        for node in nodes:
            node_type = str(node.get("nodeType", "")).upper()
            name = self._resolve_name(node.get("name", {}), locale)

            if node_type == "GROUP":
                group_item = QStandardItem(name)
                group_item.setEditable(False)
                group_item.setSelectable(False)
                has_children = self._populate_tree(
                    node.get("children", []) or [],
                    spatialDataSourceIdByLayerId,
                    locale,
                    group_item,
                )
                if has_children:
                    parent_item.appendRow(group_item)
                    kept_any = True
            elif node_type == "LAYER":
                layer_id = node.get("id")
                if layer_id in spatialDataSourceIdByLayerId:
                    layer_item = QStandardItem(name)
                    layer_item.setEditable(False)
                    layer_item.setData(
                        {
                            "id": layer_id,
                            "spatialDataSourceId": spatialDataSourceIdByLayerId[layer_id],
                        },
                        Qt.ItemDataRole.UserRole,
                    )
                    parent_item.appendRow(layer_item)
                    kept_any = True

        return kept_any

    def _on_filter_text_changed(self, text: str):
        self._proxy.setFilterFixedString(text)
        self.target_layer_tree_view.expandAll()

    def _on_mode_toggled(self, mode: ExportSelectedLayerData.ExportMode, checked: bool):
        if not checked:
            return

        is_replace = mode == ExportSelectedLayerData.ExportMode.replace
        self.layer_replace_label.setEnabled(is_replace)
        # In replace mode the Export button is enabled only once a layer is selected.
        self.export_layer_pushButton.setEnabled(mode == ExportSelectedLayerData.ExportMode.create)

        if is_replace and self.JMap_project_combo_box.currentData():
            project_id = self.JMap_project_combo_box.currentData().project_id
            self._load_project_layers(project_id, self._selected_layer_type)
        else:
            self.error_label.clear()
            self.layer_replace_label.setEnabled(False)
            self._clear_layer_tree()

        self.layer_export_mode_changed.emit(mode)

    def _on_tree_selection_changed(self, selected, deselected):
        payload = self._selected_target_payload()
        if payload:
            self.export_layer_pushButton.setEnabled(True)
            self.selected_layer_id_to_replace.emit(payload)
        else:
            # A group (non-selectable) or nothing valid is selected.
            self.export_layer_pushButton.setEnabled(False)

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

        def _can_user_modify_project(project: dict) -> bool:
            project_id = project["id"]
            reply = self.jmap_mcs.get_project_permissions(project_id)

            if reply is None or reply.status != QNetworkReply.NetworkError.NoError:
                return False

            if len(reply.content) == 0:
                return False

            permissions_payload = reply.content[0]["permissions"] or []

            return (
                Permission.MODIFY.value in permissions_payload
                or Permission.OWNER.value in permissions_payload
            )

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

            self.JMap_project_combo_box.clear()

            projects = list(filter(lambda p: _can_user_modify_project(p), projects))

            if not projects:
                self.JMap_project_combo_box.clear()
                self.error_label.setText(self.tr("No projects found"))
                self.JMap_project_combo_box.setEnabled(False)
                self.export_layer_pushButton.setEnabled(False)
                return

            for project in sorted(projects, key=lambda p: _project_display_name(p).lower()):
                project_data = ProjectData(
                    project_id=project["id"],
                    name=project["name"],
                    description=project["description"],
                    default_language=project["defaultLanguage"],
                )

                self.JMap_project_combo_box.addItem(_project_display_name(project), project_data)

            try:
                self.JMap_project_combo_box.currentIndexChanged.disconnect(
                    self._on_project_selected
                )
            except TypeError:
                pass

            self.JMap_project_combo_box.currentIndexChanged.connect(self._on_project_selected)
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
