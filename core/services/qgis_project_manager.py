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

import re
from enum import Enum

from qgis.core import (
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsLayerTreeNode,
    QgsProject,
    QgsRasterLayer,
    QgsSettings,
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
from JMapCloud.core.qgs_message_bar_handler import QgsMessageBarHandler
from JMapCloud.core.services.jmap_services_access import JMapDAS, JMapMCS, JMapMIS
from JMapCloud.core.services.qgis_project_style_manager import QGISProjectStyleManager
from JMapCloud.core.services.request_manager import RequestManager
from JMapCloud.core.views import ProjectData
from JMapCloud.ui.py_files.action_dialog import ActionDialog
from JMapCloud.ui.py_files.warning_dialog import WarningDialog


class QGISProjectManager(QObject):
    project_loaded = pyqtSignal()
    error_occurred = pyqtSignal(str)

    """
    class that handle  JMap project transfer
    """

    class ProjectVectorType(Enum):
        Default = 0
        GeoJson = 1
        VectorTiles = 2

    def __init__(self, project_data: ProjectData, layer_type):
        super().__init__()
        self.project_data = project_data
        self.project_vector_type = self.ProjectVectorType(layer_type)
        self.style_manager = QGISProjectStyleManager()
        self.project = QgsProject.instance()
        self.action_dialog = ActionDialog()
        self.errors = []
        self.layers = []

    def load_project_data(self):
        self.action_dialog.show_dialog()
        self.action_dialog.progressBar.setValue(0)
        self.action_dialog.progressBar.setFormat("%p%")
        self.action_dialog.progress_info_label.setText("Initializing loading")
        self.action_dialog.exit_pushButton.setEnabled(False)
        self.action_dialog.exit_pushButton.hide()
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
        signal = RequestManager.multi_request_async(requests)
        signal.connect(lambda replies: self.load_project(replies))

    def load_project(self, replies: dict[str, RequestManager.ResponseData]):
        """
        Load the jmap project in QGIS
        this method call all the other method to load the project
        """
        # get all project data

        for id, reply in replies.items():
            if reply.status != QNetworkReply.NetworkError.NoError or not bool(reply.content):
                message = f"error loading {id}"
                self._handle_error(message)
                return
        # project_data = replies["project-data"].content
        layers_data = replies["layers-data"].content
        layer_order = replies["layer-order"].content
        layer_groups = replies["layer-groups"].content
        mapbox_styles = replies["mapbox-styles"].content
        graphql_style_data = replies["graphql-style-data"].content

        labels_config = self.style_manager.format_JMap_label_configs(layers_data, self.project_data.default_language)
        formatted_layers_properties = self.style_manager.format_properties(
            mapbox_styles, graphql_style_data, labels_config
        )
        if formatted_layers_properties == None or labels_config == None:
            message = "error formatting styles"
            self._handle_error(message)
            return
            # -----------------------------------------------------------

        # init the progress bar of the action dialog
        self.action_dialog.progressBar.setRange(0, len(layers_data) + 1)
        self.action_dialog.progressBar.setValue(1)
        self.action_dialog.progress_info_label.setText("Initializing loading")

        # load all project's layers in the correct format
        nodes = {str: QgsLayerTreeNode}
        for i, layer_data in enumerate(layers_data):
            self.action_dialog.progress_info_label.setText(
                f"Loading layer : {layer_data['name'][self.project_data.default_language]}"
            )
            # load WMS layer. They are not serve by JMap Cloud
            if layer_data["type"].upper() == "WMS":
                # create group of layer because QGIS cannot get all selected sub-layer at once
                groupName = layer_data["name"][self.project_data.default_language]
                group = QgsLayerTreeGroup(groupName)
                group.setCustomProperty(
                    "plugins/customTreeIcon/icon",
                    ":/images/themes/default/mIconRasterGroup.svg",
                )
                # get uri foreach selected sub-layer
                properties = formatted_layers_properties[layer_data["id"]]
                layer_data["layers"] = JMapMCS.get_wms_layer_uri(properties["sources"][0])
                if not bool(layer_data["layers"]):
                    message = f"Error getting Layer {layer_data['name'][self.project_data.default_language]}"
                    QgsMessageBarHandler.send_message_to_message_bar(
                        message, "Error loading layer", level=Qgis.Critical
                    )
                    continue

                # add sub-layer in group
                for layer_name, uri in layer_data["layers"].items():

                    raster_layer = QgsRasterLayer(uri, layer_name, "wms")
                    if not raster_layer.isValid():
                        message = (
                            f"Layer {layer_data['name'][self.project_data.default_language]} is not a valid wms layer"
                        )
                        QgsMessageBarHandler.send_message_to_message_bar(
                            message, "Error loading layer", level=Qgis.Critical
                        )
                        continue

                    self.layers.append(raster_layer)
                    # self.project.addMapLayer(raster_layer, addToLegend=False)
                    group.insertChildNode(0, QgsLayerTreeLayer(raster_layer))

                if len(group.children()) > 0:
                    nodes[layer_data["id"]] = group

            # load raster layer
            elif layer_data["type"].upper() == "RASTER":
                uri = JMapMIS.get_raster_layer_uri(layer_data["spatialDataSourceId"], self.project_data.organization_id)
                raster_layer = QgsRasterLayer(uri, layer_data["name"][self.project_data.default_language], "wms")
                if raster_layer.isValid():
                    self.layers.append(raster_layer)
                    # self.project.addMapLayer(raster_layer, addToLegend=False)
                    nodes[layer_data["id"]] = QgsLayerTreeLayer(raster_layer)
                else:
                    message = f"Layer {layer_data['name'][self.project_data.default_language]} is not valid"
                    QgsMessageBarHandler.send_message_to_message_bar(
                        message, "Error loading layer", level=Qgis.Critical
                    )

            if layer_data["type"].upper() == "VECTOR":
                # if vector layer can be modified (allowClientSideEditing = True), they are serve as MVT else As geojson
                # load geojson layer
                if self.project_vector_type == self.ProjectVectorType.GeoJson or (
                    layer_data["allowClientSideEditing"] and self.project_vector_type == self.ProjectVectorType.Default
                ):
                    uri = JMapDAS.get_vector_layer_uri(
                        layer_data["spatialDataSourceId"], self.project_data.organization_id
                    )
                    vector_layer = QgsVectorLayer(uri, layer_data["name"][self.project_data.default_language], "oapif")
                    if vector_layer.isValid():
                        # set layer style
                        renderer = self.style_manager.get_layer_styles(
                            formatted_layers_properties[layer_data["id"]]["styleRules"]
                        )
                        vector_layer.setRenderer(renderer)

                        # set layer label
                        labeling = self.style_manager.get_layer_labels(
                            formatted_layers_properties[layer_data["id"]]["label"]
                        )
                        vector_layer.setLabelsEnabled(True)
                        vector_layer.setLabeling(labeling)

                        # set layer mouse over
                        if (
                            "mouseOverConfiguration" in layer_data
                            and "text" in layer_data["mouseOverConfiguration"]
                            and self.project_data.default_language in layer_data["mouseOverConfiguration"]["text"]
                        ):
                            text_label = convert_jmap_text_expression(
                                layer_data["mouseOverConfiguration"]["text"][self.project_data.default_language]
                            )
                            vector_layer.setMapTipTemplate(f"[%{text_label}%]")

                        edit_rights, all_rights = self._check_editing_rights(layer_data["permissions"])
                        if not edit_rights:
                            vector_layer.setReadOnly(True)
                        elif edit_rights and not all_rights:
                            vector_layer.editingStarted.connect(
                                lambda layer_permissions=layer_data["permissions"]: self._layer_editing_warning(
                                    layer_permissions
                                )
                            )

                        # add layer
                        self.layers.append(vector_layer)
                        # self.project.addMapLayer(vector_layer, addToLegend=False)
                        nodes[layer_data["id"]] = QgsLayerTreeLayer(vector_layer)
                    else:
                        message = f"Layer {layer_data['name'][self.project_data.default_language]} is not valid"
                        QgsMessageBarHandler.send_message_to_message_bar(
                            message, "Error loading layer", level=Qgis.Critical
                        )
                # load MVT layer

                elif self.project_vector_type == self.ProjectVectorType.VectorTiles or (
                    not layer_data["allowClientSideEditing"]
                    and self.project_vector_type == self.ProjectVectorType.Default
                ):
                    uri = JMapDAS.get_vector_tile_uri(
                        layer_data["spatialDataSourceId"], self.project_data.organization_id
                    )
                    style_groups = self.style_manager.get_mvt_layer_styles(
                        formatted_layers_properties[layer_data["id"]]["styleRules"], layer_data["elementType"]
                    )
                    labeling = self.style_manager.get_mvt_layer_labels(
                        formatted_layers_properties[layer_data["id"]]["label"], layer_data["elementType"]
                    )

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
                    for styles in style_groups:
                        vector_tile_layer = QgsVectorTileLayer(uri, styles["name"])
                        if vector_tile_layer.isValid():
                            # set layer style
                            renderer = QgsVectorTileBasicRenderer()
                            renderer.setStyles(styles["style_list"])
                            vector_tile_layer.setRenderer(renderer)

                            # set layer label
                            vector_tile_layer.setLabelsEnabled(True)
                            vector_tile_layer.setLabeling(labeling.clone())

                            # add the layer to the group
                            self.layers.append(vector_tile_layer)
                            # self.project.addMapLayer(vector_tile_layer, addToLegend=False)
                            node_layer = QgsLayerTreeLayer(vector_tile_layer)
                            group.insertChildNode(0, node_layer)
                            # set layer icon
                            node_layer.setCustomProperty(
                                "plugins/customTreeIcon/icon",
                                ":/images/themes/default/styleicons/singlebandpseudocolor.svg",
                            )
                        else:
                            message = f"Layer {layer_data['name'][self.project_data.default_language]} is not valid"
                            QgsMessageBarHandler.send_message_to_message_bar(
                                message, "Error loading layer", level=Qgis.Critical
                            )
                    if len(group.children()) > 0:
                        nodes[layer_data["id"]] = group

                self.action_dialog.progressBar.setValue(i + 2)

        self.action_dialog.progress_info_label.setText(f"Finalization...")

        for layer in self.layers:
            self.project.addMapLayer(layer, addToLegend=False)

        # add layers to the legend
        root = self.project.layerTreeRoot()
        root.setHasCustomLayerOrder(True)
        layer_ordered = root.customLayerOrder()

        self._sort_layer_tree_layer(root, layer_groups, nodes)

        # order layers rendering
        new_layer_order = []
        for index_data in reversed(layer_order):
            if index_data["id"] in nodes:
                node = nodes[index_data["id"]]
                if isinstance(node, QgsLayerTreeGroup):
                    for child_node in node.children():
                        layer = child_node.layer()
                        new_layer_order.append(layer)
                else:
                    layer = node.layer()
                    new_layer_order.append(layer)
        new_layer_order.extend(layer_ordered)
        root.setCustomLayerOrder(new_layer_order)

        """
        # set project data
        if self.project_data.crs != None:
            crs = QgsCoordinateReferenceSystem(self.project_data.crs)

            extend = self._format_initial_extends(project_data["initialExtent"])
            self.project.viewSettings().setPresetFullExtent(
                QgsReferencedRectangle(
                    QgsRectangle(extend["xmin"], extend["ymin"], extend["xmax"], extend["ymax"]), crs
                )
            )
            setting = QgsSettings().value("app/projections/newProjectCrsBehavior")

            QgsSettings().setValue("app/projections/newProjectCrsBehavior", "UsePresetCrs")
            self.project.setCrs(crs)
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
        # Finalization
        message = "<h3>Project loaded successfully</h3>"

        crs = QgsCoordinateReferenceSystem(self.project_data.crs)
        setting = QgsSettings().value("app/projections/newProjectCrsBehavior")
        if setting != "UsePresetCrs":
            message += (
                "<h4>Warning</h4>"
                "<p>The crs behavior for new project was set to 'Use Crs Of First Layer Added'</p>"
                "<p>This setting may change the project crs</p>"
                f"<p>The JMap Cloud project crs is : {crs.authid()}</p>"
            )
        else:
            actual_crs = self.project.crs()
            if crs.authid() != actual_crs.authid():
                message += (
                    "<h4>Warning</h4>"
                    "<p>The JMap Cloud project crs is different from the actual crs of the project</p>"
                    f"<p>The crs set in JMap Cloud project is : {crs.authid()}</p>"
                )

        self.action_dialog.progress_info_label.setText(f"Project loaded successfully")
        self.action_dialog.action_finished(message, False)

        self.project_loaded.emit()
        print("project loaded")

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

    def _layer_editing_warning(self, layer_permissions: list) -> None:
        message = """
            <h1>Warning</h1>
            <p>You don't have all the right to edit this layer</p>
            <p>Some changes made on this layer may not be pushed to the JMap Cloud project</p>
            <p>Here are the rights you have on this layer:</p><br>
            <style>
              table {border-collapse: collapse;}
              td {
                border:solid, 2px, black;
                padding: 10px;
              }
            </style>
            <table>
            """
        for permission in VECTOR_LAYER_EDIT_PERMISSIONS:
            message += f"<tr><td>{permission}</td><td>{'O' if permission in layer_permissions else'X'}</td></tr>"
        message += "</table>"
        self.warning_dialog = WarningDialog(message)
        self.warning_dialog.show()

    def _sort_layer_tree_layer(self, root: QgsLayerTreeNode, layer_groups: list[dict], nodes: list[QgsLayerTreeNode]):
        """
        Recursive method to sort the layer tree based on the layer order from the JMap Cloud
        :param root: The root of the layer tree
        :param layer_groups: The list of layer groups from the JMap Cloud
        :param nodes: The list of layer tree nodes
        """
        for index_data in layer_groups:
            if index_data["nodeType"].upper() == "GROUP":
                group = QgsLayerTreeGroup(index_data["name"][self.project_data.default_language], index_data["visible"])
                root.insertChildNode(-1, group)
                group.setCustomProperty(
                    "plugins/customTreeIcon/icon",
                    ":/images/themes/default/mIconFolder.svg",
                )
                self._sort_layer_tree_layer(group, index_data["children"], nodes)
            elif index_data["nodeType"].upper() == "LAYER":
                if index_data["id"] in nodes:
                    node = nodes[index_data["id"]]
                    node.setItemVisibilityChecked(index_data["visible"])
                    root.insertChildNode(-1, node)

    def _format_initial_extends(self, initial_extends: dict) -> dict:
        match = re.search(r"\([\d\,\. -]+\)", initial_extends)
        if not match:
            return None
        polygon = re.split(r",?\s+", match.group(0)[1:-1])
        polygon = [float(x) for x in polygon]

        return {
            "xmin": polygon[0],
            "ymin": polygon[1],
            "xmax": polygon[4],
            "ymax": polygon[5],
        }

    def _handle_error(self, message: str) -> None:
        self.action_dialog.action_finished(message, True)
        QgsMessageBarHandler.send_message_to_message_bar(message, "Error loading project", level=Qgis.Critical)
        self.error_occurred.emit(message)
