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


from enum import Enum

from qgis.core import (
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsProject,
    QgsRasterLayer,
    QgsTask,
    QgsVectorLayer,
    QgsVectorTileBasicRenderer,
    QgsVectorTileLayer,
)
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from JMapCloud.core.constant import (
    API_MCS_URL,
    VECTOR_LAYER_EDIT_PERMISSIONS,
    _base_url,
)
from JMapCloud.core.plugin_util import convert_jmap_text_expression
from JMapCloud.core.services.jmap_services_access import JMapDAS, JMapMCS, JMapMIS
from JMapCloud.core.services.qgis_project_style_manager import QGISProjectStyleManager
from JMapCloud.core.services.request_manager import RequestManager
from JMapCloud.core.tasks.custom_qgs_task import CustomQgsTask
from JMapCloud.core.tasks.import_style_task import (
    ImportVectorStyleTask,
    ImportVectorTilesStyleTask,
)
from JMapCloud.core.views import ProjectData, ProjectLayersData
from JMapCloud.ui.py_files.action_dialog import ActionDialog

TOTAL_STEPS = 3
MESSAGE_CATEGORY = "LoadProjectTask"


class ProjectVectorType(Enum):
    Default = 0
    GeoJson = 1
    VectorTiles = 2


class ImportProjectManager(QObject):
    """
    class that handle  JMap project transfer
    """

    project_loaded = pyqtSignal()
    error_occurred = pyqtSignal(str)
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ImportProjectManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            super().__init__()
            self.action_dialog = ActionDialog()
            self.feedback = self.action_dialog.feedback()
            self.errors = []
            self.current_step = 0
            self.importing_project = False
            self._cancel = False
            self._initialized = True
            self.tasks = []

    @staticmethod
    def instance() -> "ImportProjectManager":
        return ImportProjectManager()

    def init_import(self, project_data: ProjectData, project_vector_type: str):
        if self._cancel:
            return
        self.importing_project = True
        self.action_dialog.show_dialog()
        self.action_dialog.set_progress(0, "Initializing loading")
        self.action_dialog.progressBar.setFormat("%p%")
        self.action_dialog.set_cancelable_mode("<h3>Project importation canceled</h3>")
        self.feedback.canceled.connect(self.cancel)

        self.project_data = project_data
        self.project_vector_type = project_vector_type
        self.nodes: dict[str:QgsLayerTreeNode] = {}

        def next_function(replies):
            self.project_layers_data = self.check_project_layers_data(replies)
            self.current_step += 1
            self._set_progress(0, self.current_step)
            self.load_project()
            print("task:", len(QgsApplication.taskManager().tasks()))

        self.get_project_layers_data().connect(next_function)

    def load_project(self):
        """
        Load the jmap project in QGIS
        this method call all the other method to load the project
        """

        self.project_vector_type = ProjectVectorType(self.project_vector_type)
        self.project = QgsProject.instance()
        layers_data = self.project_layers_data.layers_data
        layers_properties = self.project_layers_data.layers_properties

        # init the progress bar of the action dialog

        # load all project's layers in the correct format
        self.layer_to_load = len(layers_data)
        for layer_data in layers_data:
            if self._cancel:
                return
            # load WMS layer. They are not serve by JMap Cloud
            if layer_data["type"].upper() == "WMS":
                layer_properties = layers_properties[layer_data["id"]]
                self.load_wms_layer(layer_data, layer_properties["sources"])
                self.is_all_layer_loaded()
            # load raster layer
            elif layer_data["type"].upper() == "RASTER":
                self.load_raster_layer(layer_data)
                self.is_all_layer_loaded()
            elif layer_data["type"].upper() == "VECTOR":
                layer_properties = layers_properties[layer_data["id"]]
                # if vector layer can be modified (allowClientSideEditing = True), they are serve as MVT else As geojson
                # load geojson layer
                if self.project_vector_type == ProjectVectorType.GeoJson or (
                    layer_data["allowClientSideEditing"] and self.project_vector_type == ProjectVectorType.Default
                ):

                    def on_finish(renderers, labeling, layer_data=layer_data):
                        print("finish loading vector layer")
                        self.load_geojson_layer(layer_data, renderers, labeling)
                        self.is_all_layer_loaded()

                    task = ImportVectorStyleTask(layer_properties)
                    task.import_style_completed.connect(on_finish)
                    task.taskTerminated.connect(self.is_all_layer_loaded)
                    task.error_occurred.connect(self.error_occurred)
                    QgsApplication.taskManager().addTask(task)
                    print("task:", len(QgsApplication.taskManager().tasks()))
                # load MVT layer
                elif self.project_vector_type == ProjectVectorType.VectorTiles or (
                    not layer_data["allowClientSideEditing"] and self.project_vector_type == ProjectVectorType.Default
                ):

                    def function(layer_properties=layer_properties, element_type=layer_data["elementType"]):
                        print("finish loading mvt layer")
                        style_groups = QGISProjectStyleManager.get_mvt_layer_styles(
                            layer_properties["styleRules"], element_type
                        )
                        labeling = QGISProjectStyleManager.get_mvt_layer_labels(layer_properties["label"], element_type)
                        renderers = {}
                        for styles in style_groups:
                            renderer = QgsVectorTileBasicRenderer()
                            renderer.setStyles(styles["style_list"])
                            renderers[styles["name"]] = renderer

                        return renderer, labeling

                    def on_finish(renderers, labeling, layer_data=layer_data):
                        self.load_mvt_layer(layer_data, renderers, labeling)
                        self.is_all_layer_loaded()

                    task = ImportVectorTilesStyleTask(layer_properties, layer_data["elementType"])
                    task.import_style_completed.connect(on_finish)
                    task.taskTerminated.connect(self.is_all_layer_loaded)
                    task.error_occurred.connect(self.error_occurred)
                    QgsApplication.taskManager().addTask(task)
                    print("task:", len(QgsApplication.taskManager().tasks()))
                else:
                    message = f"Unknown error when loading vector layer : {layer_data['name'][self.project_data.default_language]}"
                    self.error_occur(message, MESSAGE_CATEGORY)
                    self.is_all_layer_loaded()
            else:
                message = f"Unsupported layer {layer_data['name'][self.project_data.default_language]} of type {layer_data['type']}"
                self.error_occur(message, MESSAGE_CATEGORY)
        print("end")
        print("task:", len(QgsApplication.taskManager().tasks()))

    def load_wms_layer(self, layer_data: dict, sources) -> bool:
        return

        # create group of layer because QGIS cannot get all selected sub-layer at once
        groupName = layer_data["name"][self.project_data.default_language]
        group = QgsLayerTreeGroup(groupName)
        group.setCustomProperty(
            "plugins/customTreeIcon/icon",
            ":/images/themes/default/mIconRasterGroup.svg",
        )
        # get uri foreach selected sub-layer
        layer_data["layers"] = JMapMCS.get_wms_layer_uri(sources[0])

        if not bool(layer_data["layers"]):
            message = f"Error getting Layer {layer_data['name'][self.project_data.default_language]}"
            self.error_occur(message, MESSAGE_CATEGORY)
            return False

        # add sub-layer in group
        for layer_name, uri in layer_data["layers"].items():
            print(uri)
            raster_layer = QgsRasterLayer(uri, layer_name, "wms")
            if not raster_layer.isValid():
                message = f"Layer {layer_data['name'][self.project_data.default_language]} is not a valid wms layer"
                self.error_occur(message, MESSAGE_CATEGORY)
                continue
            self.project.addMapLayer(raster_layer, addToLegend=False)
            group.insertChildNode(0, QgsLayerTreeLayer(raster_layer))

        if len(group.children()) > 0:
            self.nodes[layer_data["id"]] = group
            return True
        else:
            return False

    def load_raster_layer(self, layer_data: dict) -> bool:
        uri = JMapMIS.get_raster_layer_uri(layer_data["spatialDataSourceId"], self.project_data.organization_id)
        raster_layer = QgsRasterLayer(uri, layer_data["name"][self.project_data.default_language], "wms")
        if raster_layer.isValid():
            self.project.addMapLayer(raster_layer, addToLegend=False)
            self.nodes[layer_data["id"]] = QgsLayerTreeLayer(raster_layer)
            return True
        else:
            message = f"Layer {layer_data['name'][self.project_data.default_language]} is not valid"
            self.error_occur(message, MESSAGE_CATEGORY)
            return False

    def load_geojson_layer(self, layer_data: dict, renderer, labeling) -> bool:
        uri = JMapDAS.get_vector_layer_uri(layer_data["spatialDataSourceId"], self.project_data.organization_id)
        vector_layer = QgsVectorLayer(uri, layer_data["name"][self.project_data.default_language], "oapif")
        if vector_layer.isValid():
            # set layer style
            vector_layer.setRenderer(renderer)

            # set layer label
            vector_layer.setLabelsEnabled(True)  # define that a labeling config exist
            vector_layer.setLabeling(labeling)

            # set layer mouse over
            if "mouseOverConfiguration" in layer_data and "text" in layer_data["mouseOverConfiguration"]:
                text = layer_data["mouseOverConfiguration"]["text"]
                if self.project_data.default_language in text:
                    text = text[self.project_data.default_language]
                else:
                    text = next(iter(text))
                text_label = convert_jmap_text_expression(text)
                vector_layer.setMapTipTemplate(f"[%{text_label}%]")

            edit_rights, all_rights = self._check_editing_rights(layer_data["permissions"])
            if not edit_rights:
                vector_layer.setReadOnly(True)
            elif edit_rights and not all_rights:
                vector_layer.editingStarted.connect(
                    lambda layer_permissions=layer_data["permissions"]: self._layer_editing_warning(layer_permissions)
                )

            # add layer
            self.project.addMapLayer(vector_layer, addToLegend=False)
            self.nodes[layer_data["id"]] = QgsLayerTreeLayer(vector_layer)
            return True
        else:
            message = f"Layer {layer_data['name'][self.project_data.default_language]} is not valid"
            self.error_occur(message, MESSAGE_CATEGORY)
            return False

    def load_geojson_style(layer_properties):
        print("loading vector layer")
        renderer = QGISProjectStyleManager.get_layer_styles(layer_properties["styleRules"])
        labeling = QGISProjectStyleManager.get_layer_labels(layer_properties["label"])

        return renderer, labeling

    def load_mvt_layer(self, layer_data: dict, renderers, labeling) -> bool:
        uri = JMapDAS.get_vector_tile_uri(layer_data["spatialDataSourceId"], self.project_data.organization_id)

        # We need to create a new layer for each style because rule based styles are not supported by MVT
        # create a layer group
        groupName = f'{layer_data["name"][self.project_data.default_language]}_{layer_data["elementType"]}'
        group = QgsLayerTreeGroup(groupName)
        # set group icon
        group.setCustomProperty(
            "plugins/customTreeIcon/icon",
            ":/images/themes/default/mActionAddVectorTileLayer.svg",
        )
        # create a layer for each style
        for name, renderer in renderers.items():
            vector_tile_layer = QgsVectorTileLayer(uri, name)
            if vector_tile_layer.isValid():
                # set layer style
                vector_tile_layer.setRenderer(renderer)

                # set layer label
                vector_tile_layer.setLabelsEnabled(True)  # specify that a labeling config exist
                vector_tile_layer.setLabeling(labeling.clone())

                # add the layer to the group
                node_layer = QgsLayerTreeLayer(vector_tile_layer)
                self.project.addMapLayer(vector_tile_layer, addToLegend=False)
                group.insertChildNode(0, node_layer)
                # set layer icon
                node_layer.setCustomProperty(
                    "plugins/customTreeIcon/icon",
                    ":/images/themes/default/styleicons/singlebandpseudocolor.svg",
                )
            else:
                message = f"Layer {layer_data['name'][self.project_data.default_language]} is not valid"
                self.error_occur(message, MESSAGE_CATEGORY)
        if len(group.children()) > 0:
            self.nodes[layer_data["id"]] = group
            return True
        else:
            return False

    def load_mvt_style() -> bool:
        return

    def is_all_layer_loaded(self):
        self.layer_to_load -= 1
        print(self.layer_to_load)
        if self.layer_to_load == 0:
            self.finalization()

    def finalization(self):
        if self._cancel:
            return

        finalization_total_steps = 3
        finalization_current_step = 0
        # add layers to the project
        self.action_dialog.set_text(f"Adding layers to the project")

        layer_groups = self.project_layers_data.layer_groups
        layer_order = self.project_layers_data.layer_order
        project = QgsProject.instance()

        self.action_dialog.set_text(f"Loading layer groups")
        finalization_current_step += 1
        self._set_progress(finalization_current_step / finalization_total_steps * 100, self.current_step)

        # add layers to the legend
        root = project.layerTreeRoot()
        root.setHasCustomLayerOrder(True)
        layer_ordered = root.customLayerOrder()

        self._sort_layer_tree_layer(root, layer_groups, self.nodes)

        self.action_dialog.set_text(f"Loading layer order")
        finalization_current_step += 1
        self._set_progress(finalization_current_step / finalization_total_steps * 100, self.current_step)

        # order layers rendering
        new_layer_order = []
        for index_data in reversed(layer_order):
            if index_data["id"] in self.nodes:
                node = self.nodes[index_data["id"]]
                if isinstance(node, QgsLayerTreeGroup):
                    for child_node in node.children():
                        new_layer_order.append(child_node.layer())
                else:
                    new_layer_order.append(node.layer())
        new_layer_order.extend(layer_ordered)
        root.setCustomLayerOrder(new_layer_order)

        """
        # set project data
        if self.project_data.crs != None:
            crs = QgsCoordinateReferenceSystem(self.project_data.crs)

            extend = self._format_initial_extends(project_data["initialExtent"])
            project.viewSettings().setPresetFullExtent(
                QgsReferencedRectangle(
                    QgsRectangle(extend["xmin"], extend["ymin"], extend["xmax"], extend["ymax"]), crs
                )
            )
            setting = QgsSettings().value("app/projections/newProjectCrsBehavior")

            QgsSettings().setValue("app/projections/newProjectCrsBehavior", "UsePresetCrs")
            project.setCrs(crs)
            if setting != "UsePresetCrs":
                html = (
                    "<h1>Warning</h1>"
                    "<p>The crs behavior for new project was set to 'Use Crs Of First Layer Added'</p>"
                    "<p>This setting was changed to 'Use Preset Crs' to be able to set the JMap Cloud crs of the project</p>"
                    "<p>You can change the crs behavior in the menu option <strong>settings -> options -> CRS and Transforms -> CRS Handling</strong></p>"
                )
                warning = WarningDialog(html)
                warning.show()
        """
        self.finish()

    def get_project_layers_data(self) -> pyqtSignal:
        urls = {
            # "project-data": f"{API_MCS_URL}/organizations/{self.project_data.organization_id}/projects/{self.project_data.project_id}",
            "layers-data": f"{API_MCS_URL}/organizations/{self.project_data.organization_id}/projects/{self.project_data.project_id}/layers",
            "layer-order": f"{API_MCS_URL}/organizations/{self.project_data.organization_id}/projects/{self.project_data.project_id}/layers-order",
            "layer-groups": f"{API_MCS_URL}/organizations/{self.project_data.organization_id}/projects/{self.project_data.project_id}/layers-groups",
            "mapbox-styles": f"{API_MCS_URL}/organizations/{self.project_data.organization_id}/projects/{self.project_data.project_id}/mapbox-styles",
        }
        requests = []
        for id, url in urls.items():
            requests.append(RequestManager.RequestData(url, type="GET", id=id))

        query = (
            """{
            getStyleRules(organizationId: """
            f'"{self.project_data.organization_id}"'
            """,projectId: """
            f'"{self.project_data.project_id}"'
            """, locale: """
            f'"{self.project_data.default_language}"'
            """){
                id
                layerId
                name
                conditions{
                    id
                    name
                    styleMapScales{
                        id
                        styleId
                    }
                }
            }
        }"""
        )
        variables = {}
        body = {"query": query, "variables": variables}
        headers = {"Organizationid": self.project_data.organization_id}  # do not change Organizationid
        requests.append(
            RequestManager.RequestData(f"{_base_url}/api/mcs/graphql", headers, body, "POST", id="graphql-style-data")
        )
        return RequestManager.multi_request_async(requests)

    def check_project_layers_data(self, replies: dict[str, RequestManager.ResponseData]) -> ProjectLayersData:
        self.project_layers_data = ProjectLayersData()

        for reply in replies.values():
            if reply.status != QNetworkReply.NetworkError.NoError:
                return None

        self.project_layers_data.layer_groups = replies["layer-groups"].content
        self.project_layers_data.layer_order = replies["layer-order"].content
        self.project_layers_data.layers_data = replies["layers-data"].content

        layers_data = replies["layers-data"].content
        mapbox_styles = replies["mapbox-styles"].content
        graphql_style_data = replies["graphql-style-data"].content

        labels_config = QGISProjectStyleManager.format_JMap_label_configs(
            layers_data, self.project_data.default_language
        )
        formatted_layers_properties = QGISProjectStyleManager.format_properties(
            mapbox_styles, graphql_style_data, labels_config
        )
        if formatted_layers_properties == None or labels_config == None:
            message = "error formatting styles"
            self._handle_error(message)
            return None
            # -------

        self.project_layers_data.layers_properties = formatted_layers_properties

        return self.project_layers_data

    def _check_editing_rights(self, layer_permissions: list) -> tuple[bool, bool]:
        edit_right = False
        all_rights = True

        for permission in layer_permissions:
            if permission == "EXTRACT_FEATURE":
                continue
            if permission in VECTOR_LAYER_EDIT_PERMISSIONS:
                edit_right = True
            else:
                all_rights = False
        return edit_right, all_rights

    def _sort_layer_tree_layer(self, root: QgsLayerTreeNode, layer_groups: list[dict]):
        """
        Recursive method to sort the layer tree based on the layer order from the JMap Cloud
        :param root: The root of the layer tree
        :param layer_groups: The list of layer groups from the JMap Cloud
        :param self.nodes: The list of layer tree self.nodes
        """
        for index_data in layer_groups:
            if index_data["nodeType"].upper() == "GROUP":
                group = QgsLayerTreeGroup(index_data["name"][self.project_data.default_language], index_data["visible"])
                root.insertChildNode(-1, group)
                group.setCustomProperty(
                    "plugins/customTreeIcon/icon",
                    ":/images/themes/default/mIconFolder.svg",
                )
                self._sort_layer_tree_layer(group, index_data["children"], self.nodes)
            elif index_data["nodeType"].upper() == "LAYER":
                if index_data["id"] in self.nodes:
                    node = self.nodes[index_data["id"]]
                    node.setItemVisibilityChecked(index_data["visible"])
                    root.insertChildNode(-1, node)

    def _handle_error(self, message: str) -> None:
        self.action_dialog.action_finished(message, False)
        self.error_occurred.emit(message)

    def _set_progress(self, value: float, current_step: int = None, message: str = None):
        total_progress = (current_step * 100 + value) / TOTAL_STEPS
        self.action_dialog.set_progress(total_progress, message)

    def finish(self):
        project = QgsProject.instance()
        self._set_progress(0, TOTAL_STEPS)
        self.action_dialog.set_text(f"Finalization...")

        message = "<h3>Project loaded successfully</h3>"

        crs = QgsCoordinateReferenceSystem(self.project_data.crs)
        actual_crs = project.crs()
        if crs.authid() != actual_crs.authid():
            message += (
                "<h4>Warning</h4>"
                "<p>The JMap Cloud project crs is different from the actual crs of the project</p>"
                f"<p>The crs set in JMap Cloud project is : {crs.authid()}</p>"
            )

        if len(self.errors) > 0:
            message += "<h4>Some errors occurred during the import:</h4>"
            for error in self.errors:
                message += f"<p>{error}</p>"

        self.action_dialog.action_finished(message, False)

        self.importing_project = False
        self.project_loaded.emit()
        self.action_dialog = ActionDialog()
        self.feedback = self.action_dialog.feedback()
        self.current_step = 0
        self.errors = []

    def cancel(self):
        self._cancel = True
        self.importing_project = False
        self.action_dialog = ActionDialog()
        self.feedback = self.action_dialog.feedback()
        self.current_step = 0
        self.errors = []

    def is_importing_project(self):
        return self.importing_project


#    def _format_initial_extends(self, initial_extends: dict) -> dict:
#        match = re.search(r"\([\d\,\. -]+\)", initial_extends)
#        if not match:
#            return None
#        polygon = re.split(r",?\s+", match.group(0)[1:-1])
#        polygon = [float(x) for x in polygon]
#
#        return {
#            "xmin": polygon[0],
#            "ymin": polygon[1],
#            "xmax": polygon[4],
#            "ymax": polygon[5],
#        }
