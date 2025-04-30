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


# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load Jmap class from file Jmap.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """

    from .jmap_cloud import JMap

    return JMap(iface)
