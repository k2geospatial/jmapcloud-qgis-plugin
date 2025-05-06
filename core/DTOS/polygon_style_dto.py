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
from qgis.core import (
    QgsFillSymbol,
    QgsImageFillSymbolLayer,
    QgsRasterFillSymbolLayer,
    QgsRasterLineSymbolLayer,
    QgsSimpleFillSymbolLayer,
    QgsSimpleLineSymbolLayer,
    QgsSVGFillSymbolLayer,
    QgsSymbolLayer,
)
from qgis.PyQt.QtCore import Qt

from JMapCloud.core.DTOS.style_dto import StyleDTO
from JMapCloud.core.plugin_util import (
    convert_measurement_to_pixel,
    convert_pen_style_to_dash_array,
    image_to_base64,
    opacity_to_transparency,
    transparency_to_opacity,
)


class PolygonStyleDTO(StyleDTO):
    fillColor: str
    """value in hexadecimal: #00FF00"""
    borderThickness: int
    borderColor: str
    """value in hexadecimal: #00FF00"""
    borderTransparency: int
    """value between: 0 and 100"""
    patternData: str
    """value in base64"""
    borderDashPattern: list[int]
    """value in pair of int ex: [1, 1], [1,3,5,4]"""
    borderPatternData: str
    """value in base64"""

    def __init__(self):
        super().__init__(self.StyleDTOType.POLYGON)

    @classmethod
    def from_symbol(cls, symbol: QgsFillSymbol) -> list["PolygonStyleDTO"]:
        dtos = super().from_symbol(symbol)
        for dto in dtos:
            if isinstance(dto, cls):
                dto.borderTransparency = opacity_to_transparency(
                    transparency_to_opacity(dto.borderTransparency) * symbol.opacity()
                )

        return dtos

    @classmethod
    def from_symbol_layer(cls, symbol_layer: QgsSymbolLayer) -> "PolygonStyleDTO":
        dto = cls()
        if isinstance(symbol_layer, QgsSimpleFillSymbolLayer):
            dto.fillColor = symbol_layer.color().name()
            dto.transparency = opacity_to_transparency(symbol_layer.color().alphaF())
            dto.borderColor = symbol_layer.strokeColor().name()
            dto.borderTransparency = opacity_to_transparency(symbol_layer.strokeColor().alphaF())
            width = symbol_layer.strokeWidth()
            if width == 0:
                dto.borderThickness = 0
            else:
                dto.borderThickness = max(1, round(convert_measurement_to_pixel(width, symbol_layer.strokeWidthUnit())))

            border_pen_style = symbol_layer.strokeStyle()
            if border_pen_style == Qt.PenStyle.NoPen:
                dto.borderTransparency = 100
            dto.borderDashPattern = convert_pen_style_to_dash_array(border_pen_style, dto.borderThickness)

        elif isinstance(symbol_layer, QgsImageFillSymbolLayer):
            if isinstance(symbol_layer, QgsSVGFillSymbolLayer):
                dto.patternData = image_to_base64(symbol_layer.svgFilePath())
            elif isinstance(symbol_layer, QgsRasterFillSymbolLayer):
                dto.patternData = image_to_base64(symbol_layer.imageFilePath())
                dto.transparency = opacity_to_transparency(symbol_layer.opacity())
            else:
                return None

        elif isinstance(symbol_layer, QgsSimpleLineSymbolLayer):
            width = symbol_layer.width()
            if width == 0:
                dto.borderThickness = 0
            else:
                dto.borderThickness = max(1, round(convert_measurement_to_pixel(width, symbol_layer.widthUnit())))
            dto.borderColor = symbol_layer.color().name()
            dto.borderTransparency = opacity_to_transparency(symbol_layer.color().alphaF())
            dto.fillColor = symbol_layer.color().name()
            dto.transparency = 100  # only border, no fill
            if symbol_layer.useCustomDashPattern():
                dash_pattern = convert_measurement_to_pixel(
                    symbol_layer.customDashVector(), symbol_layer.customDashPatternUnit()
                )
                dto.borderDashPattern = [
                    v / dto.borderThickness for v in dash_pattern
                ]  # because Mapbox dash-array is value * lineWidth

        elif isinstance(symbol_layer, QgsRasterLineSymbolLayer):
            width = symbol_layer.width()
            if width == 0:
                dto.borderThickness = 0
            else:
                dto.borderThickness = max(1, round(convert_measurement_to_pixel(width, symbol_layer.widthUnit())))
            dto.borderTransparency = opacity_to_transparency(symbol_layer.color().alphaF())
            dto.patternData = image_to_base64(symbol_layer.path())
            dto.transparency = 100  # only border, no fill
            dto.fillColor = symbol_layer.color().name()
        else:
            return None

        return dto
