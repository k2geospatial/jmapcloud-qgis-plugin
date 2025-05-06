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

from JMapCloud.core.DTOS.style_dto import StyleDTO
from JMapCloud.core.plugin_util import (
    image_to_base64,
    opacity_to_transparency,
    symbol_to_SVG_base64,
    transparency_to_opacity,
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
        super().__init__(self.StyleDTOType.POINT)
        self.rotationLocked = False
        self.proportional = False

    # could change in the future TODO
    @classmethod
    def from_symbol(cls, symbol: QgsMarkerSymbol) -> list["PointStyleDTO"]:
        if all(
            [
                isinstance(symbol_layer, QgsRasterMarkerSymbolLayer)
                or isinstance(symbol_layer, QgsSvgMarkerSymbolLayer)
                for symbol_layer in symbol.symbolLayers()
            ]
        ):
            return super().from_symbol(symbol)
        else:
            base64_symbol = symbol_to_SVG_base64(symbol)
            dto = cls()
            dto.symbolData = base64_symbol
            dto.transparency = opacity_to_transparency(symbol.opacity())
            return [dto]

    @classmethod
    def from_symbol_layer(cls, symbol_layer: QgsMarkerSymbolLayer) -> "PointStyleDTO":
        style = cls()

        style.size = 0.5  # this handle the pixel ratio of 2 of Mapbox spites
        offset = symbol_layer.offset()
        style.symbolOffset = {"x": offset.x(), "y": offset.y()}
        style.rotation = round(symbol_layer.angle())

        if isinstance(symbol_layer, QgsRasterMarkerSymbolLayer):
            style.symbolData = image_to_base64(symbol_layer.path())
            style.transparency = opacity_to_transparency(symbol_layer.opacity())
        elif isinstance(symbol_layer, QgsSvgMarkerSymbolLayer):
            style.symbolData = image_to_base64(symbol_layer.path())
        else:
            return None

        return style
