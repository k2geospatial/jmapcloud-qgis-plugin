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


class CriteriaDTO(DTO):
    attributeName: str
    operator: str
    value: str

    def __init__(self, attributeName: str = None, operator: str = None, value: str = None):
        super().__init__()
        self.attributeName = attributeName
        self.operator = operator
        self.value = value
