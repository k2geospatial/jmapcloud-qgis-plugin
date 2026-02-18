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

from qgis.core import QgsApplication, QgsAuthMethodConfig

from ..constant import (
    ACCESS_TOKEN_SETTING_ID,
    AUTH_CONFIG_ID,
    EXPIRATION_SETTING_ID,
    ORGANIZATION_SETTING_ID,
    REFRESH_TOKEN_SETTING_ID,
    USERNAME_SETTING_ID,
)


class SessionManager:
    def __init__(self):
            self.claims = self.get_auth_settings()

    def set_claims(self, claims):
        self.claims = claims

    def get_claims(self):
        return self.claims

    def get_organization_id(self):
        if self.claims and "organizationId" in self.claims:
            return self.claims["organizationId"]
        return None

    def get_access_token(self):
        if self.claims and "accessToken" in self.claims:
            return self.claims["accessToken"]
        return None

    def store_auth_settings(
        self,
        access_token: str = None,
        refresh_token: str = None,
        expiration: str = None,
        organization_id: str = None,
        username: str = None,
    ) -> None:
        """
        Store JMap authentication settings in QgsApplication.authManager()
        :param access_token: The access token returned by JMap's authentication API
        :param refresh_token: The refresh token returned by JMap's authentication API
        :param expiration: The expiration of the access token returned by JMap's authentication API
        :param organization_id: The id of the JMap organization
        :param username: The username of the authenticated user
        :return: None
        """

        auth_manager = QgsApplication.authManager()
        if refresh_token != None:
            auth_manager.storeAuthSetting(REFRESH_TOKEN_SETTING_ID, refresh_token, True)
        if expiration != None:
            auth_manager.storeAuthSetting(EXPIRATION_SETTING_ID, expiration, True)
        if organization_id != None:
            auth_manager.storeAuthSetting(ORGANIZATION_SETTING_ID, organization_id, True)
        if username != None:
            auth_manager.storeAuthSetting(USERNAME_SETTING_ID, username, True)
        if access_token != None:
            auth_manager.storeAuthSetting(ACCESS_TOKEN_SETTING_ID, access_token, True)
            self.store_auth_config(access_token)

    def store_auth_config(self, access_token: str = None) -> None:
        """
        Store JMap authentication config in QgsApplication.authManager()
        :param access_token: The access token returned by JMap's authentication API
        :return: None
        """

        auth_config = QgsAuthMethodConfig("APIHeader")
        auth_config.setId(AUTH_CONFIG_ID)
        auth_config.setName("JMap_Session")
        auth_config.setConfig("Authorization", "Bearer {}".format(access_token))
        QgsApplication.authManager().storeAuthenticationConfig(auth_config, True)

    def get_auth_settings(self) -> dict:
        """
        Get JMap authentication settings from QgsApplication.authManager()
        :return: A dictionary with the following keys:
            accessToken: The access token returned by JMap's authentication API
            refreshToken: The refresh token returned by JMap's authentication API
            expiration: The expiration of the access token returned by JMap's authentication API
            organizationId: The id of the JMap organization
            username: The username of the authenticated user
        """
        auth_manager = QgsApplication.authManager()
        claims = {
            "accessToken": (auth_manager.authSetting(ACCESS_TOKEN_SETTING_ID, defaultValue="", decrypt=True) or None),
            "refreshToken": (auth_manager.authSetting(REFRESH_TOKEN_SETTING_ID, defaultValue="", decrypt=True) or None),
            "expiration": (auth_manager.authSetting(EXPIRATION_SETTING_ID, defaultValue="", decrypt=True) or None),
            "organizationId": (
                auth_manager.authSetting(ORGANIZATION_SETTING_ID, defaultValue="", decrypt=True) or None
            ),
            "username": (auth_manager.authSetting(USERNAME_SETTING_ID, defaultValue="", decrypt=True) or None),
        }

        return claims

    def revoke_session(self) -> None:
        auth_manager = QgsApplication.authManager()
        auth_manager.removeAuthSetting(ACCESS_TOKEN_SETTING_ID)
        auth_manager.removeAuthSetting(REFRESH_TOKEN_SETTING_ID)
        auth_manager.removeAuthSetting(EXPIRATION_SETTING_ID)
        auth_manager.removeAuthSetting(ORGANIZATION_SETTING_ID)
        auth_manager.removeAuthSetting(USERNAME_SETTING_ID)
        auth_config = QgsAuthMethodConfig("APIHeader")
        auth_config.setId(AUTH_CONFIG_ID)
        auth_config.setName("JMap_Session")
        auth_config.setConfig("Authorization", f"")
        auth_manager.storeAuthenticationConfig(auth_config, True)
        self.set_claims(None)
