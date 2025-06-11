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

DEFAULT_BACKGROUND_COLOR = "#ffffff"
DEFAULT_SELECTION_COLOR = "#ffff00"
DEFAULT_MEASUREMENT_CRS = "EPSG:3857"
DEFAULT_UNIT = "METER"
DEFAULT_LANGUAGE = "en"
DEFAULT_PROJECT_NAME = "New Project"


class ProjectDTO(DTO):

    def __init__(
        self,
        mapCrs: str,
        name: dict[str, str] = {DEFAULT_LANGUAGE: DEFAULT_PROJECT_NAME},
        description: dict[str, str] = {},
        measurementCrs: str = DEFAULT_MEASUREMENT_CRS,
        initialExtent="null",
        backgroundColor: str = DEFAULT_BACKGROUND_COLOR,
        defaultSelectionColor: str = DEFAULT_SELECTION_COLOR,
        defaultLanguage: str = DEFAULT_LANGUAGE,
        rotation: float = 0.0,
        tags: str = [],
    ):
        super().__init__()
        self.name = name
        self.description = description
        self.mapCrs = mapCrs
        self.measurementCrs = measurementCrs
        self.mapUnit = DEFAULT_UNIT
        self.distanceUnit = DEFAULT_UNIT
        self.displayUnit = DEFAULT_UNIT
        self.initialExtent = initialExtent
        self.backgroundColor = backgroundColor
        self.defaultSelectionColor = defaultSelectionColor
        self.defaultLanguage = defaultLanguage
        self.rotation = rotation
        self.tags = tags
