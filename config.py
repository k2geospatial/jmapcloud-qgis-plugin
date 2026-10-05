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

# _env = "dev"
# _env = "qa"
_env = "prod"

if _env == "dev":
    CONFIG = {
        "API_URL": "https://api.dev-akiss.jmapcloud.io",
        "AUTH_CONFIG_ID": "JMAuthD",
        "AUTH0_DOMAIN": "auth-dev-vps.jmapcloud.io",
        "AUTH0_CLIENT_ID": "4wJU1lBMprAOeBZsVbk4TeOHOauvE3ZH",
        "AUTH0_AUDIENCE": "https://dev-vps.jmapcloud.io/",
        "JMAP_CLAIM_NAMESPACE": "https://dev-vps.jmapcloud.io",
    }

elif _env == "qa":
    CONFIG = {
        "API_URL": "https://api.qa.jmapcloud.io",
        "AUTH_CONFIG_ID": "JMAuthQ",
        "AUTH0_DOMAIN": "auth-qa.jmapcloud.io",
        "AUTH0_CLIENT_ID": "C0F38jqNKXq5GXS1jSgFrByTQLNzXX80",
        "AUTH0_AUDIENCE": "https://qa.jmapcloud.io/",
        "JMAP_CLAIM_NAMESPACE": "https://qa.jmapcloud.io",
    }

elif _env == "prod":
    CONFIG = {
        "API_URL": "https://api.jmapcloud.io",
        "AUTH_CONFIG_ID": "JMAuthP",
        "AUTH0_DOMAIN": "auth.jmapcloud.io",
        "AUTH0_CLIENT_ID": "U0J5X34n4m00NBgSWX0uCLm1FQFeodh7",
        "AUTH0_AUDIENCE": "https://jmapcloud.io/",
        "JMAP_CLAIM_NAMESPACE": "https://jmapcloud.io",
    }
