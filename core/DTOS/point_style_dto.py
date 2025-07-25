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
import math

import numpy
from qgis.core import (
    QgsMarkerSymbol,
    QgsMarkerSymbolLayer,
    QgsRasterMarkerSymbolLayer,
    QgsSvgMarkerSymbolLayer,
)
from qgis.PyQt.QtCore import QPointF, QSize

from .style_dto import StyleDTO
from ..plugin_util import (
    SVG_to_base64,
    calculate_height_symbol_layer,
    convert_measurement_to_pixel,
    opacity_to_transparency,
    image_to_base64,
    resolve_point_svg_params,
    symbol_to_SVG_base64,
)


class PointStyleDTO(StyleDTO):
    size: int
    rotation: float
    """value between: -360 and 360"""
    rotationLocked: bool
    proportional: bool
    proportionalScale: int
    symbolOffset: dict
    symbolData: str
    """value in base64"""

    def __init__(self):
        super().__init__(self.StyleDTOType.POINT)
        self.rotationLocked = False
        self.proportional = False
        self.size = 1
    
        
    @classmethod
    def from_symbol_layer(cls, symbol_layer: QgsMarkerSymbolLayer) -> "PointStyleDTO":
        dto = cls()
        symbol_layer = symbol_layer.clone()
        dto.size = 1

        dto.rotation = symbol_layer.angle()
        symbol_layer.setAngle(0)

        offset = cls.apply_JMap_rotation_to_point(dto.rotation, symbol_layer.offset())
        offset_unit = symbol_layer.offsetUnit()
        x = round(convert_measurement_to_pixel(offset.x(), offset_unit))
        y = round(convert_measurement_to_pixel(offset.y(), offset_unit))
        dto.symbolOffset = {"x": x, "y": -y}
        symbol_layer.setOffset(QPointF(0, 0))

        if isinstance(symbol_layer, QgsRasterMarkerSymbolLayer):
            width =  int(convert_measurement_to_pixel(symbol_layer.size(), symbol_layer.sizeUnit()))
            height =  int(convert_measurement_to_pixel(calculate_height_symbol_layer(symbol_layer), symbol_layer.sizeUnit()))
            dto.symbolData = image_to_base64(symbol_layer.path(), QSize(width, height))
            dto.transparency = opacity_to_transparency(symbol_layer.opacity())
            # dto.size = 1  # this handle the pixel ratio of 2 of Mapbox spites
        elif isinstance(symbol_layer, QgsSvgMarkerSymbolLayer):
            svg_parsed = resolve_point_svg_params(symbol_layer)
    
            if len(svg_parsed) == 0:
                return None
            
            dto.symbolData = SVG_to_base64(svg_parsed)
            # dto.size = 1  # this handle the pixel ratio of 2 of Mapbox spites
        else:
            symbol = QgsMarkerSymbol.createSimple(symbol_layer.properties())
            base64_symbol = symbol_to_SVG_base64(symbol)
            dto.symbolData = base64_symbol
            dto.transparency = opacity_to_transparency(symbol_layer.color().alphaF())
            del symbol
            # dto.size = 1

        return dto

    @staticmethod
    def apply_JMap_rotation_to_point(angle: float, point: QPointF) -> QPointF:
        angle = numpy.radians(angle)
        rotation_matrix = numpy.array([[math.cos(angle), -math.sin(angle)], [math.sin(angle), math.cos(angle)]])
        vector_matrix = numpy.array([[point.x()], [point.y()]])
        result = numpy.matmul(rotation_matrix, vector_matrix)
        return QPointF(result[0], result[1])
