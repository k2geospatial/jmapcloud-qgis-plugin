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
    QgsMarkerSymbol,
    QgsMarkerSymbolLayer,
    QgsRasterMarkerSymbolLayer,
    QgsSvgMarkerSymbolLayer,
)
from qgis.PyQt.QtCore import QSize

from JMapCloud.core.DTOS.style_dto import StyleDTO
from JMapCloud.core.plugin_util import (
    convert_measurement_to_pixel,
    image_to_base64,
    symbol_to_SVG_base64,
)


class PointStyleDTO(StyleDTO):
    size: int
    rotation: int
    """value between: -360 and 360"""
    rotationLocked: bool
    proportional: bool
    proportionalScale: int
    symbolOffset: dict
    symbolData: str
    """value in base64"""

    def __init__(self):
        super().__init__("POINT")
        self.rotationLocked = False
        self.proportional = False

    # could change in the future TODO
    @staticmethod
    def from_symbol(symbol: QgsMarkerSymbol) -> list["PointStyleDTO"]:
        if all(
            [
                isinstance(symbol_layer, QgsRasterMarkerSymbolLayer)
                or isinstance(symbol_layer, QgsSvgMarkerSymbolLayer)
                for symbol_layer in symbol.symbolLayers()
            ]
        ):
            return [PointStyleDTO.from_symbol_layer(symbol_layer) for symbol_layer in symbol.symbolLayers()]
        else:
            base64_symbol = symbol_to_SVG_base64(symbol)
            dto = PointStyleDTO()
            dto.symbolData = base64_symbol
            dto.transparency = (1 - min(1.0, symbol.opacity())) * 100
            return [dto]

    def from_symbol_layer(symbol_layer: QgsMarkerSymbolLayer) -> "PointStyleDTO":
        style = PointStyleDTO()

        style.size = 0.5  # this handle the pixel ratio of 2 of Mapbox spites
        offset = symbol_layer.offset()
        style.symbolOffset = {"x": offset.x(), "y": offset.y()}
        style.rotation = round(symbol_layer.angle())

        if isinstance(symbol_layer, QgsRasterMarkerSymbolLayer):
            style.symbolData = image_to_base64(symbol_layer.path())
            style.transparency = (1 - min(1.0, symbol_layer.opacity())) * 100
        elif isinstance(symbol_layer, QgsSvgMarkerSymbolLayer):
            style.symbolData = image_to_base64(symbol_layer.path())
        else:
            return None

        return style
