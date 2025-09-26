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

from typing import Union
from .dto import DTO
from .labeling_config_dto import LabelingConfigDTO
from .mouse_over_config_dto import MouseOverConfigDTO


class LayerDTO(DTO):
    spatialDataSourceId: str
    name: dict[str, str]
    type: str
    layers: list[str]
    elementType: str
    description: dict[str, str]
    visible: bool
    listed: bool
    minimumZoom: Union[int, None]
    maximumZoom: Union[int, None]
    tags: list[str]
    selectable: bool
    styles: list[str]
    imageFormat: str
    attributes: list[dict[str, str]]
    mouseOverConfiguration: MouseOverConfigDTO
    labellingConfiguration: LabelingConfigDTO

    def __init__(
        self,
        spatialDataSourceId: str,
        name: dict[str, str],
        type: str,
    ):
        super().__init__()
        self.spatialDataSourceId = spatialDataSourceId
        self.name = name
        self.type = type
