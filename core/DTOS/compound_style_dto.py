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

from .style_dto import StyleDTO


class CompoundStyleDTO(StyleDTO):
    styles: list[str]

    def __init__(self):
        super().__init__(self.StyleDTOType.COMPOUND)

    @classmethod
    def from_style_ids(cls, style_ids: list[str]) -> "CompoundStyleDTO":
        dto = cls()
        dto.styles = style_ids
        return dto
