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


class DatasourceDTO(DTO):
    # attributes: list = []
    columnX: str = ""
    columnY: str = ""
    crs: str = ""
    description: str = ""
    fileId: str = ""
    indexedAttributes: list = ""
    layer: str = ""
    layers: list = []
    name: str = ""
    params: dict = {}
    tags: list[str] = []
    type: str = ""
    capabilitiesUrl: str = ""
