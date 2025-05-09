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
import uuid

from qgis.core import (
    QgsBlockingNetworkRequest,
    QgsMessageLog,
    QgsNetworkAccessManager,
    QgsNetworkReplyContent,
)
from qgis.PyQt.QtCore import QEventLoop, QObject, Qt, QUrl, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply, QNetworkRequest

from JMapCloud.core.constant import AUTH_CONFIG_ID
from JMapCloud.core.qgs_message_bar_handler import Qgis, QgsMessageBarHandler
from JMapCloud.core.services.session_manager import SessionManager
from JMapCloud.core.signal_object import TemporarySignalObject

MESSAGE_CATEGORY = "RequestManager"


class RequestManager(QObject):
    trigger_next_request = pyqtSignal()
    _instance = None
    """
    A class for making requests_data to the JMap API and handling the response and errors.
    """

    class RequestData:
        def __init__(
            self,
            url: str,
            headers: dict = {},
            body: any = None,
            type: str = "GET",
            id: str = None,
            no_auth: bool = False,
        ):
            request = RequestManager._prepare_request(url, headers, no_auth)
            self.request = request
            self.body = RequestManager._encode_body(body)
            self.type = type
            if not id:
                id = uuid.uuid4().__str__()
            self.id = id

    class ResponseData:
        def __init__(
            self,
            content: any,
            headers: dict,
            status: QNetworkReply.NetworkError = None,
            error_message: str = None,
            id=None,
        ):
            self.content = content
            self.headers = headers
            self.status = status
            self.error_message = error_message
            self.id = id

        @classmethod
        def no_reply(cls):
            return cls(None, None, None, QNetworkReply.NetworkError.UnknownContentError)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RequestManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_concurrent: int = 10):
        if not self._initialized:
            super().__init__()
            self.nam = QgsNetworkAccessManager()
            self.max_concurrent = max_concurrent
            self.active_requests = 0
            self.queue: list[tuple["RequestManager.RequestData", TemporarySignalObject]] = []
            self.finished_requests = {}
            self.pending_request = {}
            self.trigger_next_request.connect(self._send_next_request, Qt.ConnectionType.QueuedConnection)
            self._initialized = True

    @staticmethod
    def instance() -> "RequestManager":
        return RequestManager()

    def add_requests(self, request: "RequestManager.RequestData") -> pyqtSignal:
        """add a request to the queue"""
        signal_obj = TemporarySignalObject()
        self.queue.append((request, signal_obj))
        self.trigger_next_request.emit()

        return signal_obj.signal

    def _send_next_request(self):
        """execute the next request in the queue"""
        while self.queue and self.active_requests < self.max_concurrent:

            request, signal_obj = self.queue.pop(0)

            def _handle_queue_response(response: RequestManager.ResponseData, signal_obj=signal_obj):
                self.pending_request.pop(response.id)
                signal_obj.signal.emit(response)
                self.active_requests -= 1
                self._send_next_request()

            self.pending_request[request.id] = self.custom_request_async(request, _handle_queue_response)
            self.active_requests += 1

    @classmethod
    def get_request(
        cls, url: str, headers: dict = {}, error_prefix: str = "JMap Error", no_auth: bool = False
    ) -> ResponseData:
        """
        Perform an blocking GET request to a given URL.

        :param url: URL for the request
        :param headers: Optional headers to pass with the request
        :param error_prefix: Prefix to use for error messages
        :return: a ResponseData object
        """
        request_manager = QgsBlockingNetworkRequest()
        if not no_auth:
            request_manager.setAuthCfg(AUTH_CONFIG_ID)
        request = cls._prepare_request(url, headers, True)
        try:
            response = request_manager.get(request, forceRefresh=True)
            reply = request_manager.reply()
            if response != QgsBlockingNetworkRequest.ErrorCode.NoError:
                QgsMessageBarHandler.send_message_to_message_bar(
                    str(reply.content(), "utf-8"), prefix=error_prefix, level=Qgis.Warning
                )

        except Exception as e:
            QgsMessageBarHandler.send_message_to_message_bar(str(e), prefix=error_prefix, level=Qgis.Critical)
            return cls.ResponseData.no_reply()

        if response != QgsBlockingNetworkRequest.ErrorCode.NoError:
            message = "{}, {}".format(reply.errorString(), str(reply.content(), "utf-8"))
            QgsMessageBarHandler.send_message_to_message_bar(message, prefix=error_prefix, level=Qgis.Warning)
        response_data = cls._handle_reply(reply)
        reply.clear()
        return response_data

    @classmethod
    def post_request(
        cls, url: str, body=None, headers: dict = {}, error_prefix: str = "JMap Error", no_auth: bool = False
    ) -> ResponseData:
        """
        Perform an blocking POST request to a given URL.

        :param url: URL for the request
        :param body: The body of the request
        :param headers: Optional headers to pass with the request
        :param error_prefix: Prefix to use for error messages
        :return: a ResponseData object
        """
        request_manager = QgsBlockingNetworkRequest()
        if not no_auth:
            request_manager.setAuthCfg(AUTH_CONFIG_ID)
        request = cls._prepare_request(url, headers, True)
        try:
            response = request_manager.post(
                request,
                cls._encode_body(body),
                forceRefresh=True,
            )

            reply = request_manager.reply()

        except Exception as e:
            QgsMessageLog.logMessage(message, MESSAGE_CATEGORY, Qgis.Warning)
            return cls.ResponseData.no_reply()

        if response != QgsBlockingNetworkRequest.ErrorCode.NoError:
            message = "{}, {}".format(reply.errorString(), str(reply.content(), "utf-8"))
            QgsMessageLog.logMessage(message, MESSAGE_CATEGORY, Qgis.Warning)
        response_data = cls._handle_reply(reply)
        reply.clear()
        return response_data

    @classmethod
    def custom_request(cls, request_data: RequestData) -> ResponseData:
        """
        Perform a blocking custom request to a given URL.

        :param request_data: The data for the request
        :return: a ResponseData object
        """
        request_manager = QgsNetworkAccessManager.instance()
        if request_data.body is None:
            reply = request_manager.sendCustomRequest(request_data.request, request_data.type.encode())
        else:
            reply = request_manager.sendCustomRequest(
                request_data.request, request_data.type.encode(), request_data.body
            )
        loop = QEventLoop()
        reply.finished.connect(loop.quit)
        loop.exec()
        response_data = cls._handle_reply(reply, request_data.id)
        return response_data

    @classmethod
    def custom_request_async(cls, request_data: RequestData, callback: callable = None) -> QNetworkReply:
        """
        Perform an async custom request to a given URL.

        :param request_data: The data for the request
        :param callback: The callback to call when the request is finished
        you can connect the callback with the reply finished signal
        :return: The QNetworkReply object that will emit the finished signal
        """

        request_manager = QgsNetworkAccessManager.instance()
        reply = request_manager.sendCustomRequest(
            request_data.request,
            request_data.type.encode(),
            request_data.body,
        )
        if callback:

            def on_finished(reply=reply, id=request_data.id):
                reply.disconnect()
                response_data = cls._handle_reply(reply, id)
                callback(response_data)

            reply.finished.connect(on_finished)
        return reply

    @classmethod
    def multi_request_async(cls, requests_data: list[RequestData]) -> pyqtSignal:
        """
        Perform multiple async custom requests to given URLs. and emit a signal when all requests are finished

        :param requests_data: The list of data for the requests
        :return: The signal that will emit when all requests are finished
        """
        no_request_finished = 0
        replies = {}
        request_manager = cls.instance()
        signal_object = TemporarySignalObject()

        def request_counter(reply, id: str):
            nonlocal no_request_finished
            nonlocal replies
            nonlocal signal_object
            no_request_finished += 1
            replies[id] = reply
            request_manager.pending_request.pop(id)

            if no_request_finished >= len(requests_data):
                signal_object.signal.emit(replies)

        for request_data in requests_data:
            recursive_callback = lambda reply, id=request_data.id: request_counter(reply, id)
            request_manager.pending_request[request_data.id] = cls.custom_request_async(
                request_data, recursive_callback
            )
        return signal_object.signal

    @staticmethod
    def _prepare_request(url, headers: dict[str, str] = {}, no_auth: bool = False) -> QNetworkRequest:
        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        if not no_auth:
            request.setRawHeader(
                "Authorization".encode(), "Bearer {}".format(SessionManager.instance().get_access_token()).encode()
            )
        for key, value in headers.items():
            request.setRawHeader(key.encode(), value.encode())
        return request

    @staticmethod
    def _get_headers(reply) -> list:
        # get headers list as a string list
        headersList = [str(x, "utf-8") for x in reply.rawHeaderList()]
        # get headers value as a dict
        header = {header: str(reply.rawHeader(header.encode()), "utf-8") for header in headersList}
        return header

    @staticmethod
    def _encode_body(body):
        if isinstance(body, dict):
            return json.dumps(body).encode("utf-8")
        elif isinstance(body, str):
            return body.encode("utf-8")
        else:
            return body

    @classmethod
    def _handle_reply(cls, reply, id=None):
        if isinstance(reply, QgsNetworkReplyContent):
            content = reply.content()
            error_string = reply.errorString()
            if reply.rawHeader("Content-type".encode()) == b"application/json":
                if content == "":
                    content = "{}"
                content = json.loads(str(content, "utf-8"))
                if "result" in content:
                    content = content["result"]
        elif isinstance(reply, QNetworkReply):
            content = reply.readAll().data().decode("utf-8")
            if reply.rawHeader("Content-type".encode()) == b"application/json":
                if content == "":
                    content = "{}"
                content = json.loads(content)
                if "result" in content:
                    content = content["result"]

        error_code = reply.error()
        error_string = ""
        if error_code != QNetworkReply.NoError:
            QgsMessageLog.logMessage(
                cls.instance().tr("Error occurred {}").format(content), MESSAGE_CATEGORY, Qgis.Critical
            )
            reply_error_string = reply.errorString()
            if bool(reply_error_string):
                error_string += "reply : {}\n".format(reply_error_string)
            if bool(content):
                error_string += "content : {}\n".format(content)

        headers = cls._get_headers(reply)

        return cls.ResponseData(content, headers, error_code, error_string, id)
