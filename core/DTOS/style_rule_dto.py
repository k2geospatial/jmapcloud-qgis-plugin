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

from .condition_dto import ConditionDTO
from .dto import DTO


class StyleRuleDTO(DTO):
    conditions: list[ConditionDTO]
    name: dict[str, str]
    active: bool

    def __init__(self, name: dict[str, str] = None, active: bool = None, conditions: list[ConditionDTO] = None):
        super().__init__()
        self.name = name or {}
        self.active = active or True
        self.conditions = conditions or []
