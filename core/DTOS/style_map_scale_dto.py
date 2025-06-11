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

from .dto import DTO


class StyleMapScaleDTO(DTO):
    minimumZoom: int
    maximumZoom: int
    styleId: str

    def __init__(self, minimumZoom: int = None, maximumZoom: int = None, styleId: str = None):
        super().__init__()
        self.minimumZoom = minimumZoom
        self.maximumZoom = maximumZoom
        self.styleId = styleId
