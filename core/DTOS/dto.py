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

import json


class DTO:
    def to_json(self):
        return json.dumps(self.to_dict())

    def to_dict(self):
        def serialize(obj):
            if isinstance(obj, DTO):
                return obj.to_dict()
            elif isinstance(obj, list) or isinstance(obj, tuple) or isinstance(obj, set):
                return [serialize(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: serialize(v) for k, v in obj.items()}
            return obj

        return {k: serialize(v) for k, v in self.__dict__.items()}
