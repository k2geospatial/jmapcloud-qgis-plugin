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

from JMapCloud.core.DTOS.criteria_dto import CriteriaDTO
from JMapCloud.core.DTOS.dto import DTO
from JMapCloud.core.DTOS.style_map_scale_dto import StyleMapScaleDTO


class ConditionDTO(DTO):
    criteria: list[CriteriaDTO]
    styleMapScales: list[StyleMapScaleDTO]
    name: dict[str, str]

    def __init__(
        self,
        criteria: list[CriteriaDTO] = None,
        styleMapScales: list[StyleMapScaleDTO] = None,
        name: dict[str, str] = None,
    ):
        super().__init__()
        self.criteria = criteria or []
        self.styleMapScales = styleMapScales or []
        self.name = name or {}
