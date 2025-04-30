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
# -----------------------------------------------------------s

from .constant import AuthState
from .plugin_util import (
    convert_crs_to_epsg,
    convert_jmap_datetime,
    convert_measurement_to_pixel,
    convert_scale_to_zoom,
    convert_zoom_to_scale,
    find_value_in_dict_or_first,
    image_to_base64,
    qgis_data_type_name_to_mysql,
    qgis_layer_type_to_jmc,
    time_now,
)
from .qgs_message_bar_handler import QgsMessageBarHandler
from .recurring_event import RecurringEvent
from .signal_object import TemporarySignalObject
from .views import LayerData, LayerFile, ProjectData, SupportedFileType

__all__ = [
    "AuthState",
    "qgis_layer_type_to_jmc",
    "qgis_data_type_name_to_mysql",
    "convert_crs_to_epsg",
    "find_value_in_dict_or_first",
    "convert_zoom_to_scale",
    "convert_scale_to_zoom",
    "convert_measurement_to_pixel",
    "image_to_base64",
    "convert_jmap_datetime",
    "time_now",
    "QgsMessageBarHandler",
    "RecurringEvent",
    "TemporarySignalObject",
    "SupportedFileType",
    "LayerFile",
    "LayerData",
    "ProjectData",
]
