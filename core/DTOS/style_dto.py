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
import traceback
from enum import Enum, auto

from qgis.core import Qgis, QgsMessageLog, QgsSymbol

from ..plugin_util import opacity_to_transparency, transparency_to_opacity
from .dto import DTO

MESSAGE_CATEGORY = "StyleDTO"


class StyleDTO(DTO):
    class StyleDTOType(Enum):
        POINT = auto()
        LINE = auto()
        POLYGON = auto()
        COMPOUND = auto()
        IMAGE = auto()

    type: str
    """value between: 'POINT', 'LINE', 'POLYGON', 'COMPOUND', 'IMAGE'"""
    name: str
    description: str
    transparency: int
    """value between: 0 and 100"""
    tags: list[str]

    def __init__(self, type: StyleDTOType):
        super().__init__()
        self.type = type.name
        self.name = "Symbol Layer"
        self.description = ""
        self.tags = []
        self.transparency = 0

    @staticmethod
    def rendered_symbol_layers(symbol: QgsSymbol) -> list:
        """Symbol layers QGIS actually draws: disabled ones are unchecked in the
        Symbol Selector and must not be exported."""
        return [symbol_layer for symbol_layer in symbol.symbolLayers() if symbol_layer.enabled()]

    @classmethod
    def from_symbol(cls, symbol: QgsSymbol) -> list["StyleDTO"]:
        dtos = []
        for symbol_layer in cls.rendered_symbol_layers(symbol):
            dto = cls._convert_symbol_layer(symbol_layer)
            if dto is None:
                # kept in the list so the caller can report the unsupported
                # symbol layer instead of dropping it silently
                dtos.append(None)
                continue
            dto.transparency = opacity_to_transparency(
                transparency_to_opacity(dto.transparency) * symbol.opacity()
            )
            dtos.append(dto)
        return dtos

    @classmethod
    def _convert_symbol_layer(cls, symbol_layer) -> "StyleDTO":
        """
        A symbol layer this DTO cannot read is unsupported, not a failure: returning
        None lets the caller report it and keep exporting the other symbol layers.
        """

        try:
            return cls.from_symbol_layer(symbol_layer)
        except Exception:
            QgsMessageLog.logMessage(
                traceback.format_exc(), MESSAGE_CATEGORY, Qgis.MessageLevel.Warning
            )
            return None

    @classmethod
    def from_symbol_layer(cls, symbol_layer) -> "StyleDTO":
        return None
