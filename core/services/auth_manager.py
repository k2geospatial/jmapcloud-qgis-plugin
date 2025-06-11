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

from qgis.core import QgsApplication
from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from ..plugin_util import convert_jmap_datetime, time_now
from ..qgs_message_bar_handler import Qgis, QgsMessageBarHandler
from ..recurring_event import RecurringEvent
from ..services.request_manager import RequestManager
from .session_manager import SessionManager

from ..constant import (
    ACCESS_TOKEN_SETTING_ID,
    API_AUTH_URL,
    REFRESH_TOKEN_SETTING_ID,
    AuthState,
)


class JMapAuth(QObject):
    _instance = None
    refresh_auth_event: RecurringEvent
    logged_out_signal = pyqtSignal()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JMapAuth, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            super().__init__()
            self.refresh_auth_event = RecurringEvent(
                interval=240, callback=self.refresh_auth_settings, call_on_first_run=True
            )
            self.session_manager = SessionManager()
            self._initialized = True

    @staticmethod
    def instance() -> "JMapAuth":
        return JMapAuth()

    def get_auth_state(self) -> AuthState:
        """
        Get the current authentication state of the JMap user and refresh the token if needed.

        :return: One of the following enum values:
            NOT_AUTHENTICATED: The user is not authenticated.
            NO_ORGANIZATION: The user is authenticated but has no organization.
            AUTHENTICATED: The user is authenticated and has an organization.
        """
        claims = self.session_manager.get_auth_settings()
        if not claims["accessToken"] or not claims["refreshToken"] or not claims["expiration"]:
            self.logout()
            return AuthState.NOT_AUTHENTICATED

        if JMapAuth.is_token_expired(claims["expiration"]):
            QgsApplication.authManager().storeAuthSetting(ACCESS_TOKEN_SETTING_ID, "", True)
            if not claims["organizationId"]:
                self.logout()
                return AuthState.NOT_AUTHENTICATED

            claims = self.refresh_auth_settings(claims=claims)
            if not claims:
                self.logout()
                return AuthState.NOT_AUTHENTICATED

        if not claims["username"]:
            # update claims reference
            claims["username"] = JMapAuth.get_user_self()["name"]

        if not claims["organizationId"]:
            return AuthState.NO_ORGANIZATION

        return AuthState.AUTHENTICATED

    @staticmethod
    def is_token_expired(token_expiration: str) -> bool:
        """
        Check if the given token has expired.

        :param token_expiration: The expiration of the token
        :return: True if the token has expired, False otherwise
        """
        return convert_jmap_datetime(token_expiration) < time_now()

    def refresh_auth_settings(self, org_id: str = None, claims: dict = None) -> dict:
        """
        Refresh the JMap authentication settings using the provided organization ID and claims.

        :param org_id: An optional organization ID to be used for refreshing authentication settings.
        :param claims: An optional dictionary containing current authentication claims.
        :return: A dictionary with updated authentication claims if the refresh is successful, otherwise None.
        """
        if claims is None:
            claims = self.session_manager.get_auth_settings()
        if org_id:
            claims["organizationId"] = org_id
        elif "organizationId" not in claims:
            return None

        url = "{}/refresh-token".format(API_AUTH_URL)
        body = {
            "refreshToken": "{}".format(claims["refreshToken"]),
            "organizationId": claims["organizationId"],
        }
        prefix = "Authentication Error"
        response = RequestManager.post_request(url, body, error_prefix=prefix, no_auth=True)
        if response.status == QNetworkReply.NetworkError.NoError:
            content = response.content
            claims = {
                "accessToken": content["accessToken"],
                "refreshToken": content["refreshToken"],
                "expiration": content["accessTokenExpireAt"],
                "organizationId": claims["organizationId"],
                "username": claims["username"],
            }
            # ----- setup Authentication_config ------
            self.session_manager.store_auth_settings(
                access_token=content["accessToken"],
                refresh_token=content["refreshToken"],
                expiration=content["accessTokenExpireAt"],
                organization_id=claims["organizationId"],
            )
            self.session_manager.set_claims(claims)
            return claims
        elif response.status != QNetworkReply.NetworkError.UnknownNetworkError:
            self.logout(response.content["message"])
            return None
        else:
            return None

    @staticmethod
    def get_access_token(email: str, password: str) -> str:
        """
        Get an access token for the given email and password.

        :param email: The email of a JMap account
        :param password: The password of the JMap account
        :return: An access token if the authentication is successful, otherwise None
        """

        url = "{}/authenticate".format(API_AUTH_URL)
        body = {"username": email, "password": password}
        prefix = "Authentication Error"
        response = RequestManager.post_request(url, body, error_prefix=prefix, no_auth=True)

        if response.status == QNetworkReply.NetworkError.NoError:
            content = response.content
            # ----- setup Authentication_config ------
            SessionManager.store_auth_settings(
                access_token=content["accessToken"],
                refresh_token=content["refreshToken"],
                expiration=content["accessTokenExpireAt"],
            )

            return content["accessToken"]
        else:
            return None

    @staticmethod
    def get_user_self() -> dict:
        """
        Get the user associated with the given access token.

        :param access_token: An access token obtained by calling JMapAuth.get_access_token
        :return: A dictionary with the user information and all his organization ids if the request is successful, otherwise None
        """
        url = "{}/users/self".format(API_AUTH_URL)
        prefix = "Authentication Error"
        response = RequestManager.get_request(url, error_prefix=prefix)

        if response.status == QNetworkReply.NetworkError.NoError:
            SessionManager.store_auth_settings(username=response.content["name"])
            return response.content
        else:
            return None

    def logout(self, error_message: str = None) -> None:
        """
        try to revoke the access token from JMap and remove all the authentication settings from QGIS auth manager...
        """
        if error_message:
            QgsMessageBarHandler.send_message_to_message_bar(error_message, level=Qgis.Warning)

        auth_manager = QgsApplication.authManager()
        self.refresh_auth_event.stop()
        refresh_token = auth_manager.authSetting(REFRESH_TOKEN_SETTING_ID, defaultValue="", decrypt=True) or None
        if refresh_token:
            url = "{}/revoke-token".format(API_AUTH_URL)
            body = {"refreshToken": refresh_token}
            prefix = self.tr("Logout Error")
            RequestManager.post_request(url, body, error_prefix=prefix, no_auth=True)
        self.session_manager.revoke_session()
        self.logged_out_signal.emit()
