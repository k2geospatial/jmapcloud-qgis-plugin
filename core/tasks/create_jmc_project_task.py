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

from qgis.core import QgsLayerTreeGroup, QgsLayerTreeLayer, QgsLayerTreeNode
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from JMapCloud.core.constant import API_MCS_URL
from JMapCloud.core.DTOS import (
    LabelingConfigDTO,
    LayerDTO,
    MouseOverConfigDTO,
    ProjectDTO,
)
from JMapCloud.core.plugin_util import convert_QGIS_text_expression_to_JMap
from JMapCloud.core.services.jmap_services_access import JMapMCS
from JMapCloud.core.services.request_manager import RequestManager
from JMapCloud.core.tasks.custom_qgs_task import CustomQgsTask
from JMapCloud.core.views import LayerData, ProjectData

TOTAL_STEPS = 3
MESSAGE_CATEGORY = "CreateJMCProjectTask"


class CreateJMCProjectTask(CustomQgsTask):
    project_creation_finished = pyqtSignal(list)

    def __init__(self, layers_data: list[LayerData], project_data: ProjectData):
        super().__init__("Create JMC Project", CustomQgsTask.CanCancel)
        self.layers_data = layers_data
        self.project_data = project_data
        self.request_manager = RequestManager.instance()
        self.no_layers_created = 0
        self.set_total_steps(TOTAL_STEPS + len(self.layers_data))

    def run(self):
        if self.isCanceled():
            return False

        return self.create_jmc_project()

    def create_jmc_project(self):

        rectangle = {
            "x1": self.project_data.initialExtent.xMinimum(),
            "y1": self.project_data.initialExtent.yMinimum(),
            "x2": self.project_data.initialExtent.xMaximum(),
            "y2": self.project_data.initialExtent.yMaximum(),
        }

        project_dto = ProjectDTO(
            name={self.project_data.default_language: self.project_data.name},
            description={self.project_data.default_language: self.project_data.description},
            mapCrs=self.project_data.crs.authid(),
            initialExtent=rectangle,
        )
        reply = JMapMCS.post_project(self.project_data.organization_id, project_dto)
        if reply.status != QNetworkReply.NetworkError.NoError:
            self.error_occur(f"Error creating project : {reply.error_message}", MESSAGE_CATEGORY)
            return False
        content = reply.content
        self.next_steps()
        self.project_data.project_id = content["id"]

        for layer_data in self.layers_data:
            print("create layer : ", layer_data.layer_name)
            request = self.define_next_post_layer_request(layer_data)
            if request:
                reply = self.request_manager.custom_request(request)
                self.is_all_layers_style_exported(reply, layer_data)
            else:
                self.no_layers_created += 1
                layer_data.status = LayerData.Status.layer_creation_error
            self.next_steps()

        return True

    def define_next_post_layer_request(self, layer_data: LayerData):
        layer = layer_data.layer

        if layer_data.layer_type == LayerData.LayerType.file_vector:
            dto_type = "VECTOR"
        elif layer_data.layer_type == LayerData.LayerType.API_FEATURES:
            dto_type = "OGC_API_FEATURES"
        elif layer_data.layer_type == LayerData.LayerType.file_raster:
            dto_type = "RASTER"
        elif layer_data.layer_type == LayerData.LayerType.WMS_WMTS:
            dto_type = "WMS"
        else:  # TODO
            return None

        layer_dto = LayerDTO(
            layer_data.datasource_id, {self.project_data.default_language: layer_data.layer_name}, dto_type
        )
        layer_dto.description = {self.project_data.default_language: ""}  # todo
        layer_dto.visible = True
        layer_dto.listed = True
        layer_dto.spatialDataSourceId = layer_data.datasource_id
        layer_dto.tags = []
        layer_dto.selectable = True

        map_tip_template = layer.mapTipTemplate()
        mouse_over_text = None
        if bool(map_tip_template):
            mouse_over_text = MouseOverConfigDTO.convert_qgis_map_tip_template(map_tip_template)
            mouse_over_text = {self.project_data.default_language: mouse_over_text}

        if layer_data.layer_type in [LayerData.LayerType.API_FEATURES, LayerData.LayerType.file_vector]:
            layer_dto.elementType = layer_data.element_type
            layer_dto.attributes = []
            for field in layer_data.layer.fields().names():
                layer_dto.attributes.append({"name": field})

            if not bool(map_tip_template):
                display_expression = layer.displayExpression()
                mouse_over_text = convert_QGIS_text_expression_to_JMap(display_expression)
                mouse_over_text = {self.project_data.default_language: mouse_over_text}

            if layer.labelsEnabled():
                labeling = layer.labeling()
                labeling_dto = LabelingConfigDTO.from_qgs_labeling(labeling, self.project_data.default_language)
                if labeling_dto == None:
                    message = f"Error creating labeling for layer {layer_data.layer_name}, JMap Cloud only support single rule labeling"
                    self.error_occur(message, MESSAGE_CATEGORY)
                else:
                    layer_dto.labellingConfiguration = labeling_dto
        elif layer_data.layer_type == LayerData.LayerType.WMS_WMTS:
            layer_dto.layers = [layer_data.datasource_layer]
            layer_dto.styles = ["default"]
            layer_dto.imageFormat = layer_data.format

        layer_dto.mouseOverConfiguration = MouseOverConfigDTO(layer.mapTipsEnabled(), mouse_over_text)

        url = f"{API_MCS_URL}/organizations/{self.project_data.organization_id}/projects/{self.project_data.project_id}/layers"
        body = layer_dto.to_json()
        return RequestManager.RequestData(url, type="POST", body=body, id=layer_data.layer_id)

    def is_all_layers_style_exported(self, reply: RequestManager.ResponseData, layer_data: LayerData):
        print("is_all_layers_created")
        if reply.status != QNetworkReply.NetworkError.NoError:
            layer_data.status = LayerData.Status.layer_creation_error
            self.error_occur(reply.error_message, MESSAGE_CATEGORY)
        else:
            layer_data.jmc_layer_id = reply.content["id"]
        self.no_layers_created += 1
        if self.no_layers_created == len(self.layers_data):
            self._update_layers_order()
            self.next_steps()
            self._update_layer_groups(self.project_data.legendRoot)
            self.next_steps()
            self.project_creation_finished.emit(self.layers_data)

    def _update_layers_order(self) -> bool:
        layers_list_order = self.project_data.legendRoot.layerOrder()
        ids_list_order = []
        for layer in reversed(layers_list_order):
            for layer_data in self.layers_data:
                if layer.id() == layer_data.layer_id:
                    ids_list_order.append(layer_data.jmc_layer_id)
                    break

        print("update layers order")
        url = f"{API_MCS_URL}/organizations/{self.project_data.organization_id}/projects/{self.project_data.project_id}/layers-order"
        body = {"ids": ids_list_order}
        request = RequestManager.RequestData(url, body=body, type="PUT")
        response = self.request_manager.custom_request(request)
        if response.status != QNetworkReply.NetworkError.NoError:
            print("error")
            return False
        print("success")
        return True

    def _update_layer_groups(self, root: QgsLayerTreeNode, id: str = "root") -> bool:
        print("update layer groups", root.name() or "root")
        url = f"{API_MCS_URL}/organizations/{self.project_data.organization_id}/projects/{self.project_data.project_id}/layers-groups"
        layer_groups_ids = []
        root.children()
        # set lengend order and create layer-groups
        for child in root.children():
            if isinstance(child, QgsLayerTreeGroup):
                body = {"name": {self.project_data.default_language: child.name()}, "visible": True}
                request = RequestManager.RequestData(url, body=body, type="POST")
                response = self.request_manager.custom_request(request)
                if response.status != QNetworkReply.NetworkError.NoError:
                    return False
                new_id = response.content["id"]
                layer_groups_ids.append(new_id)
                self._update_layer_groups(child, new_id)
            elif isinstance(child, QgsLayerTreeLayer):
                qgis_id = child.layer().id()
                for layer_data in self.layers_data:
                    if layer_data.layer_id == qgis_id:
                        layer_groups_ids.append(layer_data.jmc_layer_id)
                        break
            else:
                raise Exception("not implemented")
        # update layer groups order
        body = {"id": id, "children": layer_groups_ids, "nodeType": "GROUP"}
        request = RequestManager.RequestData(f"{url}/{id}", body=body, type="PATCH")
        response = self.request_manager.custom_request(request)
        if response.status != QNetworkReply.NetworkError.NoError:
            print("error")
            return False
        print("success")
        return True
