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

import copy
import re

from qgis.core import (
    QgsApplication,
    QgsCategorizedSymbolRenderer,
    QgsExpression,
    QgsFeatureRenderer,
    QgsFillSymbol,
    QgsGraduatedSymbolRenderer,
    QgsLineSymbol,
    QgsMarkerSymbol,
    QgsNullSymbolRenderer,
    QgsRuleBasedRenderer,
    QgsSingleSymbolRenderer,
    QgsSymbol,
)
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from ..constant import API_MCS_URL, JMCOperator
from ..DTOS import (
    CompoundStyleDTO,
    ConditionDTO,
    CriteriaDTO,
    LineStyleDTO,
    PointStyleDTO,
    PolygonStyleDTO,
    StyleDTO,
    StyleMapScaleDTO,
    StyleRuleDTO,
)
from ..plugin_util import (
    convert_jmap_datetime,
    convert_scale_to_zoom,
    opacity_to_transparency,
    transparency_to_opacity,
)
from ..services.request_manager import RequestManager
from .custom_qgs_task import CustomQgsTask
from ..views import LayerData, ProjectData

DEFAULT_SINGLE_STYLE_RULE_NAME = "Simple Symbol"
DEFAULT_GRADUATED_STYLE_RULE_NAME = "Graduated Symbol"
DEFAULT_CATEGORIZED_STYLE_RULE_NAME = "Categorized Symbol"
MESSAGE_CATEGORY = "JMCExportLayerStyleTask"


class ExportLayersStyleTask(CustomQgsTask):
    layer_styles_exportation_finished = pyqtSignal()

    def __init__(self, layers_data: list[LayerData], project_data: ProjectData):
        super().__init__("Exporting layer style", CustomQgsTask.CanCancel)

        self.layers_data = layers_data
        self.project_data = project_data
        self.no_layer_style_exported = 0
        self.request_manager = RequestManager.instance()
        self.task_manager = QgsApplication.taskManager()

        for layer_data in self.layers_data:
            subtask = ExportLayerStyleTask(layer_data, self.project_data)
            subtask.export_layer_style_completed.connect(self._is_all_layers_style_exported)
            subtask.error_occurred.connect(self.error_occurred)
            self.addSubTask(subtask, subTaskDependency=self.SubTaskDependency.ParentDependsOnSubTask)

    def run(self):
        if self.isCanceled():
            return False
        if len(self.layers_data) == 0:
            self.layer_styles_exportation_finished.emit()
        return True

    def _is_all_layers_style_exported(self):
        self.no_layer_style_exported += 1
        if self.no_layer_style_exported == len(self.layers_data):
            self.layer_styles_exportation_finished.emit()


class ExportLayerStyleTask(CustomQgsTask):
    export_layer_style_completed = pyqtSignal()

    def __init__(self, layer_data: LayerData, project_data: ProjectData):
        super().__init__("Exporting layer style", CustomQgsTask.CanCancel)
        self.layer_data = layer_data
        self.project_data = project_data
        self.request_manager = RequestManager.instance()
        self.set_total_steps(1)

    def run(self):
        if self.isCanceled():
            return False
        if self.layer_data.layer_type in [LayerData.LayerType.file_vector, LayerData.LayerType.API_FEATURES]:
            self._handle_renderer(self.layer_data)
            self._delete_default_style_rules()
        else:
            self._patch_raster_style()
        self.export_layer_style_completed.emit()
        return True

    def _handle_renderer(self, layer: LayerData):
        renderer = layer.layer.renderer()
        default_rule_data = {
            "label": "",
            "filterExpression": [],
            "maximumZoom": None,
            "minimumZoom": None,
            "active": True,
        }

        if isinstance(renderer, QgsSingleSymbolRenderer):
            default_rule_data["label"] = DEFAULT_SINGLE_STYLE_RULE_NAME
            symbol = renderer.symbol()
            style_ids = self._export_symbol_to_style(symbol)
            style_rule_dto = StyleRuleDTO(
                name={self.project_data.default_language: DEFAULT_SINGLE_STYLE_RULE_NAME},
                active=default_rule_data["active"],
            )
            self._add_condition_to_style_rule(style_ids, default_rule_data, style_rule_dto)
            self._export_style_rules(style_rule_dto)
        elif isinstance(renderer, QgsRuleBasedRenderer):
            root_rule = renderer.rootRule()
            total = 0

            def calculate(root: QgsRuleBasedRenderer.Rule):
                nonlocal total
                for rule in root.children():
                    calculate(rule)
                    total += 1

            calculate(root_rule)
            self.set_total_steps(total)
            self._handle_rule(renderer.rootRule())
        elif isinstance(renderer, QgsGraduatedSymbolRenderer):
            layer_name = layer.uri_components["layerName"]
            fields: list[dict] = layer.layer_file.fields[layer_name]
            style_rule = StyleRuleDTO(
                {self.project_data.default_language: DEFAULT_GRADUATED_STYLE_RULE_NAME}, default_rule_data["active"]
            )
            self._add_condition_to_style_rule(style_ids, default_rule_data, style_rule)
            attribute = self._get_standardized_attribute_name(renderer.classAttribute(), fields) 
            if not bool(attribute):
                return False
            self.set_total_steps(len(renderer.ranges()) + 1)
            for range in renderer.ranges():
                default_rule_data["label"] = range.label()
                style_ids = self._export_symbol_to_style(range.symbol())
                lowerValue = range.lowerValue()
                if bool(lowerValue):
                    default_rule_data["filterExpression"].append(
                        CriteriaDTO(attributeName=attribute, operator=JMCOperator.GREATER_THAN.name, value=lowerValue)
                    )
                upperValue = range.upperValue()
                if bool(upperValue):
                    default_rule_data["filterExpression"].append(
                        CriteriaDTO(
                            attributeName=attribute, operator=JMCOperator.LOWER_OR_EQUALS_TO.name, value=upperValue
                        )
                    )
                self._add_condition_to_style_rule(style_ids, default_rule_data, style_rule)
                default_rule_data["filterExpression"] = []
                self.next_steps()
            self._export_style_rules(style_rule)
            self.next_steps()
        elif isinstance(renderer, QgsCategorizedSymbolRenderer):
            layer_name = layer.uri_components["layerName"]
            fields: list[dict] = layer.layer_file.fields[layer_name]
            style_rule = StyleRuleDTO(
                {self.project_data.default_language: DEFAULT_CATEGORIZED_STYLE_RULE_NAME}, default_rule_data["active"]
            )
            other_value_style_rule = StyleRuleDTO({self.project_data.default_language: "other values"}, True)
            attribute = self._get_standardized_attribute_name(renderer.classAttribute(), fields)
            if not bool(attribute):
                return False
            self.set_total_steps(len(renderer.categories()) + 1)
            for category in renderer.categories():
                default_rule_data["label"] = category.label()
                style_ids = self._export_symbol_to_style(category.symbol())
                value = category.value()
                if bool(value):
                    default_rule_data["filterExpression"] = [
                        CriteriaDTO(attributeName=attribute, operator=JMCOperator.EQUALS.name, value=value)
                    ]
                    self._add_condition_to_style_rule(style_ids, default_rule_data, style_rule)
                    default_rule_data["filterExpression"] = []
                else:
                    self._add_condition_to_style_rule(style_ids, default_rule_data, other_value_style_rule)
                self.next_steps()
            if len(other_value_style_rule.conditions) > 0:
                self._export_style_rules(other_value_style_rule)
            self._export_style_rules(style_rule)
            self.next_steps()
        elif isinstance(renderer, QgsNullSymbolRenderer):
            return True
        else:
            message = self.tr("Error for layer {}. Renderer type {}, not supported").format(
                self.layer_data.layer_name, type(renderer)
            )
            self.error_occur(message, MESSAGE_CATEGORY)
            return False

        self.setProgress(100)
        return True

    def _handle_rule(
        self, rule: QgsRuleBasedRenderer.Rule, rule_data: dict = None, style_rule_dto: StyleRuleDTO = None
    ) -> bool:
        if self.isCanceled():
            return False
        """
        Recursive function that handle a root-rule and its children.

        If rule_data is None, it will be created, else it will be updated following passed rule's data.\n
        If rule children exist it will be recursively called.\n
        If any rule child have symbols it will create a style rule.\n
        If symbol exist in rule it will be exported but it need a style_rule_id.\n
        """
        if not rule_data:
            rule_data = {
                "label": "",
                "filterExpression": [],
                "maximumZoom": None,
                "minimumZoom": None,
                "active": True,
            }
        # update rule data
        active = rule.active()
        if active != None:
            rule_data["active"] = rule_data["active"] and active

        label = rule.label()
        if label:
            rule_data["label"] = label

        filter_expression = self._convert_qgis_expression_to_jmc(rule.filterExpression())
        if filter_expression:
            rule_data["filterExpression"].extend(filter_expression)
        max_zoom = convert_scale_to_zoom(rule.maximumScale())
        if not rule_data["maximumZoom"]:
            rule_data["maximumZoom"] = max_zoom

        elif max_zoom and max_zoom < rule_data["maximumZoom"]:
            rule_data["maximumZoom"] = max_zoom

        min_zoom = convert_scale_to_zoom(rule.minimumScale())
        if not rule_data["minimumZoom"]:
            rule_data["minimumZoom"] = min_zoom
        elif min_zoom and min_zoom > rule_data["minimumZoom"]:
            rule_data["minimumZoom"] = min_zoom

        # export symbol if exist
        symbol = rule.symbol()
        if symbol:
            if not style_rule_dto:
                message = self.tr("Unexpected rule '{}' have symbol but no parent rule were found").format(rule.label())
                self.error_occur(message, MESSAGE_CATEGORY)
                self.add_exception(Exception(message))
                return False

            style_ids = self._export_symbol_to_style(symbol)
            self._add_condition_to_style_rule(style_ids, rule_data, style_rule_dto)

        # Create style rule if rule's children have symbols
        children = rule.children()
        style_rule_dto = None
        if any([bool(child.symbol()) for child in children]):
            style_rule_dto = StyleRuleDTO(
                {self.project_data.default_language: rule_data["label"]}, rule_data["active"], []
            )
        # recursive call
        for rule in children:
            self._handle_rule(rule, copy.deepcopy(rule_data), style_rule_dto)
            self.next_steps()
        if style_rule_dto:
            if not self._export_style_rules(style_rule_dto):
                return False

        return True

    def _add_condition_to_style_rule(self, style_ids: list[str], rule_data: dict, style_rule_dto: StyleRuleDTO):

        for style_id in style_ids:
            condition_DTO = ConditionDTO(
                rule_data["filterExpression"], name={self.project_data.default_language: rule_data["label"] or "None"}
            )
            style_map_scale = StyleMapScaleDTO(rule_data["minimumZoom"], rule_data["maximumZoom"], style_id)
            condition_DTO.styleMapScales.append(style_map_scale)
            style_rule_dto.conditions.append(condition_DTO)

    def _convert_qgis_expression_to_jmc(self, expression: str) -> list[CriteriaDTO]:  # TODO

        if not bool(expression) or not QgsExpression(expression).isValid():
            return None
        expression = expression.replace("\\", "")
        fields = self.layer_data.layer.fields().names()

        def _find_attribute(expression_part: str) -> str:
            expression_part = expression_part.strip()

            # find attribute
            pattern = {
                r"[aA][tT][tT][rR][iI][bB][uU][tT][eE]\(\s*\'(\w+)\'\s*\)": r"\1",
                r"\"(\w+)\"": r"\1",
                r"(\w+)": r"\1",
            }
            attribute = None
            for pattern, replacement in pattern.items():
                match = re.search(pattern, expression_part)
                if match:
                    attribute = re.sub(pattern, replacement, match.group(0))
                    break
            if attribute not in fields:
                return None
            return attribute

        def _find_value(expression_part: str) -> str:
            # find value
            pattern = {r"^\'(.+)\'$|^(\d+(?:.\d+)?)$": r"\1"}
            value = None
            for pattern, replacement in pattern.items():
                match = re.search(pattern, expression_part)
                if match:
                    value = re.sub(pattern, replacement, match.group(0))
                    break
            return value

        operator_translate = JMCOperator.operator_translate()
        any_operator_pattern = "|".join(operator_translate.keys())

        def _split_operator(expression: str) -> list[str]:
            parts = re.split(any_operator_pattern, expression)
            if len(parts) != 2:
                message = self.tr("invalid expression '{}', too many or no valid operators").format(expression)
                self.error_occur(message, MESSAGE_CATEGORY)
                return None
            parts.append(re.search(any_operator_pattern, expression).group(0))
            return parts

        # start
        criterias: list[CriteriaDTO] = []
        # or operator not supported
        if re.search(r"\b[oO][rR]\b", expression):
            message = self.tr("error in expression '{}'. 'OR' operator not supported in JMap Cloud").format(expression)
            self.error_occur(message, MESSAGE_CATEGORY)
            return []
        # split and expression for multiple conditions
        conditions = re.split(r"\b[aA][nN][dD]\b", expression)
        for condition in conditions:
            # split expression when find any operator
            parts = _split_operator(condition)
            if parts is None:
                message = self.tr("invalid expression '{}'").format(expression)
                self.error_occur(message, MESSAGE_CATEGORY)
                return []
            # get operator
            operator = JMCOperator.translate(parts[2].strip())
            if operator is None:
                message = self.tr("invalid operator {} in expression '{}'").format(parts[2].strip(), expression)
                self.error_occur(message, MESSAGE_CATEGORY)
                return []
            # find attribute
            attribute = _find_attribute(parts[0].strip())
            if not attribute:
                attribute = _find_attribute(parts[1].strip())
                if not attribute:
                    message = self.tr("invalid attribute in expression '{}'. Attributes: not in fileds : {}").format(
                        expression, fields
                    )
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return []
                operator = JMCOperator.reverse(operator)
                value = _find_value(parts[0].strip())
            else:
                value = _find_value(parts[1].strip())
            if not bool(value) and operator not in [JMCOperator.IS_NULL.name, JMCOperator.IS_NOT_NULL.name]:
                message = self.tr("invalid value {} in expression '{}' ").format(value, expression)
                self.error_occur(message, MESSAGE_CATEGORY)
                return []
            criteria_dto = CriteriaDTO(attribute, operator, value)
            # find value
            criterias.append(criteria_dto)
        return criterias

    def _export_symbol_to_style(self, symbol: QgsSymbol) -> list[str]:

        if isinstance(symbol, QgsMarkerSymbol):
            styles = PointStyleDTO.from_symbol(symbol)
            initial_type = "POINT"
        elif isinstance(symbol, QgsLineSymbol):
            styles = LineStyleDTO.from_symbol(symbol)
            initial_type = "LINE"
        elif isinstance(symbol, QgsFillSymbol):
            styles = PolygonStyleDTO.from_symbol(symbol)
            initial_type = "POLYGON"
        else:
            self.error_occur(
                self.tr("Unsupported symbol type '{}' for layer '{}'.").format(type(symbol), self.layer_data.layer_name),
                MESSAGE_CATEGORY,
            )
            return []

        # patch layer opacity
        for style in styles:
            style.transparency = opacity_to_transparency(
                transparency_to_opacity(style.transparency) * self.layer_data.layer.opacity()
            )
            if isinstance(style, PolygonStyleDTO):
                style.borderTransparency = opacity_to_transparency(
                    transparency_to_opacity(style.borderTransparency) * self.layer_data.layer.opacity()
                )

        style_ids = []

        url = "{}/organizations/{}/styles".format(API_MCS_URL, self.project_data.organization_id)

        # create every style (post Style)
        for style in styles:
            if style is None:
                message = self.tr("Export style error for layer '{}'. Unsupported symbol layer").format(
                    self.layer_data.layer_name
                )
                self.error_occur(message, MESSAGE_CATEGORY)
                continue
            body = style.to_json()
            request = RequestManager.RequestData(url, type="POST", body=body)
            reply = self.request_manager.custom_request(request)
            if reply.status == QNetworkReply.NetworkError.NoError:
                style_ids.append(reply.content["id"])
            else:
                message = self.tr("Export style error: {}").format(reply.error_message)
                self.error_occur(message, MESSAGE_CATEGORY)
        if initial_type != "POLYGON" and len(style_ids) > 1:
            style_ids.reverse()  # reverse order for compound style
            compound_style = CompoundStyleDTO.from_style_ids(style_ids)
            body = compound_style.to_json()
            request = RequestManager.RequestData(url, type="POST", body=body)
            reply = self.request_manager.custom_request(request)
            if reply.status == QNetworkReply.NetworkError.NoError:
                style_ids = [reply.content["id"]]
            else:
                message = self.tr("Export style error: {}").format(reply.error_message)
                self.error_occur(message, MESSAGE_CATEGORY)

            # -----------------------

        # -----------------------
        return style_ids

    def _export_style_rules(self, style_rule_dto: StyleRuleDTO):
        if len(style_rule_dto.conditions) == 0:
            message = self.tr(
                "Error exporting style rule for layer '{}': no condition in style rule to export with"
            ).format(self.layer_data.layer_name)
            self.error_occur(message, MESSAGE_CATEGORY)
            return False
        url = "{}/organizations/{}/projects/{}/layers/{}/style-rules".format(
            API_MCS_URL, self.project_data.organization_id, self.project_data.project_id, self.layer_data.jmc_layer_id
        )

        body = style_rule_dto.to_json()
        request = RequestManager.RequestData(url, type="POST", body=body)
        response = self.request_manager.custom_request(request)
        return True

    def _delete_default_style_rules(self):
        url = "{}/organizations/{}/projects/{}/layers/{}/style-rules".format(
            API_MCS_URL, self.project_data.organization_id, self.project_data.project_id, self.layer_data.jmc_layer_id
        )

        request = RequestManager.RequestData(url, type="GET")
        response = self.request_manager.custom_request(request)
        if response.status != QNetworkReply.NetworkError.NoError:
            return False
        content = response.content
        default_style_rule = None
        for style_rule in content:
            if style_rule["name"][self.project_data.default_language] == "Default rule":
                if not default_style_rule or convert_jmap_datetime(
                    default_style_rule["creationDate"]
                ) > convert_jmap_datetime(style_rule["creationDate"]):
                    default_style_rule = style_rule
        id = default_style_rule["id"]
        request = RequestManager.RequestData("{}/{}".format(url, id), type="DELETE")
        response = self.request_manager.custom_request(request)
        if response.status != QNetworkReply.NetworkError.NoError:
            return False
        return True

    def _patch_raster_style(self):
        layer = self.layer_data.layer
        dto = StyleDTO(StyleDTO.StyleDTOType.IMAGE)
        dto.transparency = opacity_to_transparency(layer.opacity())

        url = "{}/organizations/{}/projects/{}/layers/{}/style-rules".format(
            API_MCS_URL, self.project_data.organization_id, self.project_data.project_id, self.layer_data.jmc_layer_id
        )
        request_data = RequestManager.RequestData(url, type="GET")
        response = self.request_manager.custom_request(request_data)
        if response.status != QNetworkReply.NetworkError.NoError:
            error_message = self.tr("Error getting style for layer '{}': {}").format(
                self.layer_data.layer_name, response.error_message
            )
            self.error_occur(error_message, MESSAGE_CATEGORY)
            return False
        style_id = None
        try:
            style_id = response.content[0]["conditions"][0]["styleMapScales"][0]["styleId"]
        except Exception as e:
            error_message = self.tr("Error getting style for layer '{}': {}").format(self.layer_data.layer_name, e)
            self.error_occur(error_message, MESSAGE_CATEGORY)
            return False

        url = "{}/organizations/{}/styles/{}".format(API_MCS_URL, self.project_data.organization_id, style_id)
        body = dto.to_json()
        request = RequestManager.RequestData(url, type="PATCH", body=body)
        response = self.request_manager.custom_request(request)
        if response.status != QNetworkReply.NetworkError.NoError:
            error_message = self.tr("Error patching style for layer '{}': {}").format(
                self.layer_data.layer_name, response.error_message
            )
            self.error_occur(error_message, MESSAGE_CATEGORY)
            return False
        return True

    def _get_standardized_attribute_name(self, original_name: str, fields: list[dict]) -> str:
        for field in fields:
            if field["originalName"] == original_name:
                return field["standardizedName"]
        return original_name