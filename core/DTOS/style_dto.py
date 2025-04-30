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
from JMapCloud.core.DTOS.dto import DTO


class StyleDTO(DTO):
    type: str
    """value between: 'POINT', 'LINE', 'POLYGON', 'COMPOUND'"""
    name: str
    description: str
    transparency: int
    """value between: 0 and 100"""
    tags: list[str]

    def __init__(self, type: str):
        super().__init__()
        self.type = type
        self.name = "Symbol Layer"
        self.description = ""
        self.tags = []
