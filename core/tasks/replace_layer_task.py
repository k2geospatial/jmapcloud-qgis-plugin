from typing import Union

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from ..DTOS.labeling_config_dto import LabelingConfigDTO
from ..DTOS.layer_dto import UpdateLayerDTO
from ..DTOS.mouse_over_config_dto import MouseOverConfigDTO
from ..plugin_util import convert_QGIS_text_expression_to_JMap, convert_scale_to_zoom
from ..services.jmap_services_access import JMapMCS
from ..tasks.custom_qgs_task import CustomQgsTask
from ..views import ExportSelectedLayerData, LayerData

MESSAGE_CATEGORY = "ReplaceLayerTask"


class ReplaceLayerTask(CustomQgsTask):
    layer_replacement_finished = pyqtSignal(object)

    def __init__(
        self,
        jmap_mcs: JMapMCS,
        organisation_id: str,
        layer_data: LayerData,
        export_selected_layer_data: ExportSelectedLayerData,
    ):
        super().__init__(
            (
                f"Replacing layer {layer_data.layer_name}"
                f" in JMC project {export_selected_layer_data.JMC_project.name}"
            ),
            CustomQgsTask.CanCancel,
        )
        self._jmap_mcs = jmap_mcs
        self._organisation_id = organisation_id
        self._layer_data = layer_data
        self._export_selected_layer_data = export_selected_layer_data

    def run(self):
        if self.isCanceled():
            return False

        self._replace_layer_in_jmc_project()

    def _replace_layer_in_jmc_project(self):
        request_payload = self._create_layer_patch_request(self._layer_data)

        if not request_payload:
            self.error_occur(
                self.tr("Error creating request to replace layer in JMC"), MESSAGE_CATEGORY
            )
            self.layer_replacement_finished.emit(None)
            return False

        # Debug payload sent to PATCH layer endpoint.
        QgsMessageLog.logMessage(
            self.tr("PATCH layer payload: {}").format(request_payload.to_json()),
            MESSAGE_CATEGORY,
            Qgis.MessageLevel.Info,
        )

        reply = self._jmap_mcs.patch_layer(
            self._organisation_id,
            self._export_selected_layer_data.JMC_project.project_id,
            self._export_selected_layer_data.target_JMC_layer_id,
            request_payload,
        )

        if reply.status != QNetworkReply.NetworkError.NoError:
            self.error_occur(
                self.tr("Error replacing layer in JMC: {}").format(reply.error_message),
                MESSAGE_CATEGORY,
            )
            # Debug: fetch current layer definition to compare schema vs PATCH payload.
            current_layer = self._jmap_mcs.get_layer_by_id(
                self._export_selected_layer_data.JMC_project.project_id,
                self._export_selected_layer_data.target_JMC_layer_id,
            )
            QgsMessageLog.logMessage(
                self.tr("Current JMC layer payload: {}").format(current_layer.content),
                MESSAGE_CATEGORY,
                Qgis.MessageLevel.Info,
            )
            self._layer_data.status = LayerData.Status.unknown_error
            self.layer_replacement_finished.emit(self._layer_data)
            return False

        self.layer_replacement_finished.emit(self._layer_data)
        return True

    def _create_layer_patch_request(self, layer_data: LayerData) -> Union[UpdateLayerDTO, None]:
        qgis_layer = layer_data.layer

        if not qgis_layer:
            return None

        default_language = self._export_selected_layer_data.JMC_project.default_language
        layer_dto = UpdateLayerDTO()

        layer_dto.name = {default_language: layer_data.layer_name}
        layer_dto.description = {default_language: ""}
        layer_dto.visible = True
        layer_dto.listed = True
        layer_dto.selectable = True

        layer_dto.minimumZoom = (
            convert_scale_to_zoom(qgis_layer.minimumScale())
            if qgis_layer.minimumScale() != 0
            else None
        )
        layer_dto.maximumZoom = (
            convert_scale_to_zoom(qgis_layer.maximumScale())
            if qgis_layer.maximumScale() != 0
            else None
        )

        map_tip_template = qgis_layer.mapTipTemplate()
        mouse_over_text = None

        if map_tip_template:
            mouse_over_text = MouseOverConfigDTO.convert_qgis_map_tip_template(map_tip_template)
            mouse_over_text = {default_language: mouse_over_text}

        if layer_data.layer_type in [
            LayerData.LayerType.file_vector,
            LayerData.LayerType.API_FEATURES,
        ]:
            layer_dto.attributes = []

            layer_name = layer_data.uri_components.get("layerName", "defaultLayer")
            fields_by_layer = layer_data.layer_file.fields if layer_data.layer_file else {}
            if layer_name not in fields_by_layer and "defaultLayer" in fields_by_layer:
                layer_name = "defaultLayer"

            for field in fields_by_layer.get(layer_name, []):
                layer_dto.attributes.append({"name": field["standardizedName"]})

            if not mouse_over_text:
                display_expression = qgis_layer.displayExpression()
                mouse_over_text = convert_QGIS_text_expression_to_JMap(display_expression)
                mouse_over_text = {default_language: mouse_over_text}

            if qgis_layer.labelsEnabled():
                labeling = qgis_layer.labeling()
                labeling_config_dto = LabelingConfigDTO.from_qgs_labeling(
                    labeling, default_language
                )
                if not labeling_config_dto:
                    self.error_occur(
                        self.tr(
                            (
                                "Error creating labeling for layer {},"
                                "JMap Cloud only support single rule labeling"
                            )
                        ).format(layer_data.layer_name),
                        MESSAGE_CATEGORY,
                    )
                else:
                    layer_dto.labellingConfiguration = labeling_config_dto
        elif layer_data.layer_type == LayerData.LayerType.WMS_WMTS:
            layer_dto.layers = [layer_data.uri_components["layerName"]]
            layer_dto.imageFormat = layer_data.uri_components["format"]

        layer_dto.mouseOverConfiguration = MouseOverConfigDTO(
            qgis_layer.mapTipsEnabled(), mouse_over_text
        )
        return layer_dto
