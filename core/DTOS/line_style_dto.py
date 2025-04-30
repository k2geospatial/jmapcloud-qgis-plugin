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
    QgsArrowSymbolLayer,
    QgsLineSymbol,
    QgsLineSymbolLayer,
    QgsRasterLineSymbolLayer,
    QgsSimpleLineSymbolLayer,
)
from qgis.PyQt.QtCore import Qt

from JMapCloud.core.DTOS.polygon_style_dto import PolygonStyleDTO
from JMapCloud.core.DTOS.style_dto import StyleDTO
from JMapCloud.core.plugin_util import (
    convert_measurement_to_pixel,
    convert_pen_style_to_dash_array,
    image_to_base64,
)


class LineStyleDTO(StyleDTO):
    lineColor: str
    """value in hexadecimal: #00FF00"""
    arrowType: str  # unknown
    arrowPosition: float
    lineThickness: int
    lineCap: str
    """value between: 'square', 'butt'(flat), 'round'"""
    lineJoin: str
    """value between: 'bevel', 'miter', 'round'"""
    dashPattern: list[int]
    """value in pair of int ex: [1, 1], [1,3,5,4]"""
    patternData: str
    """value in base64"""

    def __init__(self):
        super().__init__("LINE")

    @staticmethod
    def from_symbol(symbol: QgsLineSymbol) -> list["LineStyleDTO"]:
        return [LineStyleDTO.from_symbol_layer(symbol_layer) for symbol_layer in symbol.symbolLayers()]

    @staticmethod
    def from_symbol_layer(symbol_layer: QgsLineSymbolLayer) -> "LineStyleDTO":
        dto = LineStyleDTO()
        dto.lineThickness = convert_measurement_to_pixel(symbol_layer.width(), symbol_layer.widthUnit())
        if isinstance(symbol_layer, QgsSimpleLineSymbolLayer):
            dto.lineColor = symbol_layer.color().name()
            line_cap = symbol_layer.penCapStyle()
            if line_cap == Qt.PenCapStyle.FlatCap:
                line_cap = "BUTT"
            elif line_cap == Qt.PenCapStyle.SquareCap:
                line_cap = "SQUARE"
            elif line_cap == Qt.PenCapStyle.RoundCap:
                line_cap = "ROUND"
            dto.lineCap = line_cap
            lineJoin = symbol_layer.penJoinStyle()
            if lineJoin == Qt.PenJoinStyle.BevelJoin:
                lineJoin = "BEVEL"
            elif lineJoin == Qt.PenJoinStyle.MiterJoin:
                lineJoin = "MITER"
            elif lineJoin == Qt.PenJoinStyle.RoundJoin:
                lineJoin = "ROUND"
            dto.lineJoin = lineJoin

            if symbol_layer.useCustomDashPattern():
                dash_pattern = convert_measurement_to_pixel(
                    symbol_layer.customDashVector(), symbol_layer.customDashPatternUnit()
                )
                dto.dashPattern = [
                    v / dto.lineThickness for v in dash_pattern
                ]  # because Mapbox dash-array is value * lineWidth
            else:
                pen_style = symbol_layer.penStyle()
                dto.dashPattern = convert_pen_style_to_dash_array(pen_style, dto.lineThickness)

            dto.transparency = 100 - symbol_layer.color().alphaF() * 100
        elif isinstance(symbol_layer, QgsRasterLineSymbolLayer):
            dto.patternData = image_to_base64(symbol_layer.path())
            dto.transparency = 100 - symbol_layer.opacity() * 100
        elif isinstance(symbol_layer, QgsArrowSymbolLayer):
            sub_symbol = symbol_layer.subSymbol()
            sub_dto = PolygonStyleDTO.from_symbol_layer(sub_symbol)
            if not sub_dto:
                return None
            fill_color = sub_dto.fillColor
            if not sub_dto.fillColor:
                fill_color = sub_symbol.color().name()
            dto.lineColor = fill_color
            dto.arrowType = symbol_layer.arrowType()  # or maybe headType()
            dto.arrowPosition = 1.0
        else:
            return None

        return dto
