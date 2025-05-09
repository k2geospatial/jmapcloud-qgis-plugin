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

import re

from JMapCloud.core.plugin_util import convert_QGIS_text_expression_to_JMap

from .dto import DTO


class MouseOverConfigDTO(DTO):
    text: dict[str, str]
    active: bool
    preventDuplication: bool
    backgroundColor: str
    "format : #RRGGBB"
    minimumZoom: int
    maximumZoom: int

    def __init__(self, active, text: dict[str, str] = {"en", ""}):
        super().__init__()
        self.text = text
        self.active = active
        self.preventDuplication = True
        self.minimumZoom = 0
        self.maximumZoom = 23
        self.backgroundColor = "#ffffff"

    @staticmethod
    def convert_qgis_map_tip_template(text) -> str:
        while True:
            match = re.search(r"\[%((?:[^[%]|\[(?!%)|%(?!]))+?)%\]", text)
            if not match:
                break
            part = convert_QGIS_text_expression_to_JMap(match.group(0)[2:-2])
            if not part:
                part = match.group(0)
            try:
                text = re.sub(r"\[%((?:[^[%]|\[(?!%)|%(?!]))+?)%\]", part, text, count=1)
            except:
                break

        return text
