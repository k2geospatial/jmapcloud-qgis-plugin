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

from typing import Union

from qgis.core import (
    Qgis,
    QgsAbstractVectorLayerLabeling,
    QgsPalLayerSettings,
    QgsRuleBasedLabeling,
    QgsTextBackgroundSettings,
    QgsVectorLayerSimpleLabeling,
)

from ..plugin_util import (
    convert_measurement_to_pixel,
    convert_QGIS_text_expression_to_JMap,
    convert_scale_to_zoom,
    symbol_to_SVG_base64,
)

from .dto import DTO


class LabelingConfigDTO(DTO):

    active: bool
    allowOverlapping: bool
    anchor: str
    "value between: CENTER, LEFT, RIGHT, TOP, BOTTOM, TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT"
    backgroundSymbolActive: bool
    backgroundSymbolData: str
    backgroundSymbolMimeType: str
    "ex: image/svg+xml"
    followMapRotation: bool
    frameActive: bool
    frameBorderColor: str
    "format: #000000"
    frameFillColor: str
    "format: #FFFFFF"
    frameTransparency: 0
    labelSpacing: 250
    maximumZoom: Union[int, None]
    minimumZoom: Union[int, None]
    offset: dict[str, int]
    "format: {y: 0, x: 0}"
    outlineColor: str
    "format: #000000"
    outlined: bool
    rotationAttribute: str
    rotationDirection: str
    "CW or CCW"
    text: dict[str, str]
    "format: {fr: " ", en: " ", es: " "}"
    textBold: bool
    textColor: str
    "format: #000000"
    textItalic: bool
    textSize: int
    transparency: int
    "0-100"

    def __init__(self):
        super().__init__()
        self.active = False
        self.allowOverlapping = False
        self.anchor = "CENTER"
        self.backgroundSymbolActive = False
        self.followMapRotation = False
        self.frameActive = False
        self.frameTransparency = 0
        self.labelSpacing = 250
        self.maximumZoom = 23
        self.minimumZoom = 0
        self.offset = {"x": 0, "y": 0}
        self.outlined = False
        self.rotationDirection = "CW"
        self.text = {"fr": "", "en": "", "es": ""}
        self.textBold = False
        self.textItalic = False
        self.textSize = 12
        self.transparency = 0

    @staticmethod
    def from_qgs_pal_layer_settings(
        labeling_setting: QgsPalLayerSettings, language: str = "en", rule: QgsRuleBasedLabeling.Rule = None
    ):
        dto = LabelingConfigDTO()
        if rule is None:
            dto.active = True
            dto.maximumZoom = convert_scale_to_zoom(labeling_setting.maximumScale) if labeling_setting.scaleVisibility else None
            dto.minimumZoom = convert_scale_to_zoom(labeling_setting.minimumScale) if labeling_setting.scaleVisibility else None
        else:
            dto.active = rule.active()
            dto.maximumZoom = convert_scale_to_zoom(rule.maximumScale())
            dto.minimumZoom = convert_scale_to_zoom(rule.minimumScale())
        
        overlap_policy = labeling_setting.placementSettings().overlapHandling()
        if overlap_policy == Qgis.LabelOverlapHandling.PreventOverlap:
            dto.allowOverlapping = False
        else:
            dto.allowOverlapping = True

        if labeling_setting.quadOffset == QgsPalLayerSettings.QuadrantPosition.QuadrantRight:
            dto.anchor = "LEFT"
        elif labeling_setting.quadOffset == QgsPalLayerSettings.QuadrantPosition.QuadrantLeft:
            dto.anchor = "RIGHT"
        elif labeling_setting.quadOffset == QgsPalLayerSettings.QuadrantPosition.QuadrantBelow:
            dto.anchor = "TOP"
        elif labeling_setting.quadOffset == QgsPalLayerSettings.QuadrantPosition.QuadrantAbove:
            dto.anchor = "BOTTOM"
        elif labeling_setting.quadOffset == QgsPalLayerSettings.QuadrantPosition.QuadrantBelowRight:
            dto.anchor = "TOP_LEFT"
        elif labeling_setting.quadOffset == QgsPalLayerSettings.QuadrantPosition.QuadrantBelowLeft:
            dto.anchor = "TOP_RIGHT"
        elif labeling_setting.quadOffset == QgsPalLayerSettings.QuadrantPosition.QuadrantAboveRight:
            dto.anchor = "BOTTOM_LEFT"
        elif labeling_setting.quadOffset == QgsPalLayerSettings.QuadrantPosition.QuadrantAboveLeft:
            dto.anchor = "BOTTOM_RIGHT"
        else:
            dto.anchor = "CENTER"

        format = labeling_setting.format()
        background = format.background()
        background_active = background.enabled()
        if background_active:
            type = background.type()
            if type in [
                QgsTextBackgroundSettings.ShapeType.ShapeMarkerSymbol,
                QgsTextBackgroundSettings.ShapeType.ShapeSVG,
            ]:
                dto.backgroundSymbolActive = True
                symbol = background.markerSymbol()
                dto.backgroundSymbolData = symbol_to_SVG_base64(symbol)
                dto.backgroundSymbolMimeType = "image/svg+xml"
            else:
                dto.frameActive = True
                dto.frameFillColor = background.fillColor().name()
                dto.frameBorderColor = background.strokeColor().name()
                dto.frameTransparency = 100 - background.opacity() * 100

        if labeling_setting.placement in [
            Qgis.LabelPlacement.Line,
            Qgis.LabelPlacement.Free,
            Qgis.LabelPlacement.Curved,
        ]:
            dto.followMapRotation = True
        else:
            dto.followMapRotation = False

        dto.offset = {"x": labeling_setting.xOffset, "y": -labeling_setting.yOffset}  # y is inverted in MapBox style

        buffer = format.buffer()
        buffer_enabled = buffer.enabled()
        if buffer_enabled:
            dto.outlined = True
            dto.outlineColor = buffer.color().name()

        dto.text = {language: convert_QGIS_text_expression_to_JMap(labeling_setting.fieldName)}

        font = format.font()
        dto.textBold = font.bold()
        dto.textColor = format.color().name()
        dto.textItalic = font.italic()
        dto.textSize = convert_measurement_to_pixel(format.size(), format.sizeUnit())
        dto.transparency = 100 - format.color().alphaF() * 100

        return dto

    @staticmethod
    def from_qgs_labeling(labeling: QgsAbstractVectorLayerLabeling, language: str = "en"):
        if isinstance(labeling, QgsRuleBasedLabeling):
            root_rule = labeling.rootRule()
            rules = root_rule.children()
            if len(rules) != 1:
                return None
            else:
                return LabelingConfigDTO.from_qgs_pal_layer_settings(rules[0].settings(), language, rules[0])
        elif isinstance(labeling, QgsVectorLayerSimpleLabeling):
            return LabelingConfigDTO.from_qgs_pal_layer_settings(labeling.settings(), language)
        else:
            raise Exception("Unsupported labeling type")
