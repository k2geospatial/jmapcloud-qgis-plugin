from typing import Union

from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from ..DTOS import LabelingConfigDTO, LayerDTO, MouseOverConfigDTO
from ..plugin_util import convert_QGIS_text_expression_to_JMap, convert_scale_to_zoom
from ..services.jmap_services_access import JMapMCS
from ..tasks.custom_qgs_task import CustomQgsTask
from ..views import LayerData, ProjectData

MESSAGE_CATEGORY = "CreateLayerTask"


class CreateLayerTask(CustomQgsTask):
    layer_creation_finished = pyqtSignal(object)

    def __init__(
        self,
        jmap_mcs: JMapMCS,
        organisation_id: str,
        layer_data: LayerData,
        JMC_project: ProjectData,
    ):
        super().__init__(
            f"Creating layer {layer_data.layer_name} in JMC project {JMC_project.name}",
            CustomQgsTask.CanCancel,
        )
        self._jmap_mcs = jmap_mcs
        self._organisation_id = organisation_id
        self._layer_data = layer_data
        self._JMC_project = JMC_project

    def run(self):
        if self.isCanceled():
            return False

        self._create_layer_in_jmc()

    def _create_layer_in_jmc(self):
        request = self._create_layer_post_request(self._layer_data)

        if not request:
            self.error_occur(
                self.tr("Error creating request to create layer in JMC"), MESSAGE_CATEGORY
            )
            self.layer_creation_finished.emit(None)
            return False

        reply = self._jmap_mcs.post_layer(
            self._organisation_id, self._JMC_project.project_id, request
        )

        if reply.status != QNetworkReply.NetworkError.NoError:
            self.error_occur(
                self.tr("Error creating layer in JMC: {}").format(reply.error_message),
                MESSAGE_CATEGORY,
            )
            self._layer_data.status = LayerData.Status.layer_creation_error
            self.layer_creation_finished.emit(self._layer_data)
            return False

        self._layer_data.jmc_layer_id = reply.content["id"]
        self.layer_creation_finished.emit(self._layer_data)
        return True

    def _create_layer_post_request(self, layer_data: LayerData) -> Union[LayerDTO, None]:
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
            layer_data.datasource_id,
            {self._JMC_project.default_language: layer_data.layer_name},
            dto_type,
        )

        layer_dto.description = {self._JMC_project.default_language: ""}  # todo
        layer_dto.visible = True
        layer_dto.listed = True
        layer_dto.minimumZoom = (
            convert_scale_to_zoom(layer.minimumScale())
            if layer.hasScaleBasedVisibility() and layer.minimumScale() > 0
            else None
        )
        layer_dto.maximumZoom = (
            convert_scale_to_zoom(layer.maximumScale())
            if layer.hasScaleBasedVisibility() and layer.maximumScale() > 0
            else None
        )
        layer_dto.spatialDataSourceId = layer_data.datasource_id
        layer_dto.tags = []
        layer_dto.selectable = True

        map_tip_template = layer.mapTipTemplate()
        mouse_over_text = None
        if bool(map_tip_template):
            mouse_over_text = MouseOverConfigDTO.convert_qgis_map_tip_template(map_tip_template)
            mouse_over_text = {self._JMC_project.default_language: mouse_over_text}

        if layer_data.layer_type in [
            LayerData.LayerType.API_FEATURES,
            LayerData.LayerType.file_vector,
        ]:
            layer_dto.elementType = layer_data.element_type
            layer_dto.attributes = []

            for field in self._resolve_layer_attributes(layer_data):
                attribute_name = field.get("standardizedName") or field.get("originalName")
                if attribute_name:
                    layer_dto.attributes.append({"name": attribute_name})

            if not bool(map_tip_template):
                display_expression = layer.displayExpression()
                mouse_over_text = convert_QGIS_text_expression_to_JMap(display_expression)
                mouse_over_text = {self._JMC_project.default_language: mouse_over_text}

            if layer.labelsEnabled():
                labeling = layer.labeling()
                labeling_dto = LabelingConfigDTO.from_qgs_labeling(
                    labeling, self._JMC_project.default_language
                )
                if labeling_dto is None:
                    message = self.tr(
                        (
                            "Error creating labeling for layer {},",
                            " JMap Cloud only support single rule labeling",
                        )
                    ).format(layer_data.layer_name)
                    self.error_occur(message, MESSAGE_CATEGORY)
                else:
                    layer_dto.labellingConfiguration = labeling_dto
        elif layer_data.layer_type == LayerData.LayerType.WMS_WMTS:
            layer_dto.layers = [layer_data.uri_components["layers"]]
            layer_dto.styles = ["default"]
            layer_dto.imageFormat = layer_data.uri_components["format"]

        layer_dto.mouseOverConfiguration = MouseOverConfigDTO(
            layer.mapTipsEnabled(), mouse_over_text
        )
        return layer_dto

    def _resolve_layer_attributes(self, layer_data: LayerData) -> list[dict]:
        if layer_data.layer_file is None:
            return []

        fields_by_layer = layer_data.layer_file.fields or {}
        requested_layer_name = (layer_data.uri_components or {}).get("layerName")

        if requested_layer_name and requested_layer_name in fields_by_layer:
            return fields_by_layer.get(requested_layer_name, [])
        if "defaultLayer" in fields_by_layer:
            return fields_by_layer.get("defaultLayer", [])
        if len(fields_by_layer) > 0:
            return fields_by_layer.get(next(iter(fields_by_layer)), [])
        return []
