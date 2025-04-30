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

_env = "dev"
# _env = "prod"

if _env == "dev":
    CONFIG = {"API_URL": "https://api.qa.jmapcloud.io"}

elif _env == "prod":
    CONFIG = {"API_URL": "https://api.jmapcloud.io"}
