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
from enum import Enum, auto

from qgis.core import QgsSymbol

from JMapCloud.core.DTOS.dto import DTO
from JMapCloud.core.plugin_util import opacity_to_transparency, transparency_to_opacity


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

    @classmethod
    def from_symbol(cls, symbol: QgsSymbol) -> list["StyleDTO"]:
        dtos = []
        for symbol_layer in symbol.symbolLayers():
            dto = cls.from_symbol_layer(symbol_layer)
            dto.transparency = opacity_to_transparency(transparency_to_opacity(dto.transparency) * symbol.opacity())
            dtos.append(dto)

        return dtos

    @classmethod
    def from_symbol_layer(cls, symbol_layer) -> "StyleDTO":
        return None
