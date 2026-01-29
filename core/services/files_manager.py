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

import base64
import math
from pathlib import Path

from qgis.PyQt.QtCore import QTimer, pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from ..constant import API_FUS_URL, API_MCS_URL
from ..DTOS.datasource_dto import DatasourceDTO
from ..plugin_util import convert_crs_to_epsg
from ..recurring_event import RecurringEvent
from .request_manager import RequestManager
from ..tasks.custom_qgs_task import CustomTaskManager
from ..views import LayerData, LayerFile, SupportedFileType

CHUNK_SIZE = 1024 * 1024 * 5  # 5MB
MESSAGE_CATEGORY = "FilesUploadManager"


class FilesUploadManager(CustomTaskManager):
    tasks_completed = pyqtSignal(list)
    step_title_changed = pyqtSignal(str)

    def __init__(self, layers_data: list[LayerData], layer_files: list[LayerFile], organization_id: str):
        super().__init__("FilesUploadManager")
        self.layers_data: list[LayerData] = layers_data
        self.layer_files: list[LayerFile] = layer_files
        self.files_to_analyze: list[str] = []
        self.file_uploaders: list[FileUploader] = []
        self.organization_id = organization_id
        self._num_file_uploaded = 0
        self.progress = [0] * len(layer_files)
        self.total_steps = len(self.layer_files)
        self.request_manager = RequestManager.instance()
        self._cancel = False

    def run(self):
        if self._cancel:
            return False

        self.set_total_steps(len(self.layer_files))
        if len(self.layer_files) == 0:
            self.progress_changed.emit(100.0)
            self.tasks_completed.emit(self.layers_data)
            return True
        self.step_title_changed.emit(self.tr("Uploading layers files"))
        for i, layer_file in enumerate(self.layer_files):
            file_uploader = FileUploader(layer_file, self.organization_id)

            def error_occurred(error_message, layer_file=layer_file):
                layer_file.upload_status = LayerFile.Status.uploading_error
                error_message = self.tr("Error uploading file {}: {}".format(layer_file.file_path, error_message))
                self.error_occur(error_message, MESSAGE_CATEGORY)

            def progress_changed(progress, ref):
                self.progress[ref] = progress
                total_progress = sum(self.progress) / len(self.progress)
                self.progress_changed.emit(total_progress)

            file_uploader.error_occurred.connect(error_occurred)
            file_uploader.progress_changed.connect(lambda progress, ref=i: progress_changed(progress, ref))

            def next_func(jmc_file_id):
                self.is_all_files_uploaded(jmc_file_id)

            file_uploader.tasks_completed.connect(next_func)
            self.file_uploaders.append(file_uploader)
            file_uploader.init_upload()
        return True

    def cancel(self):
        self._cancel = True
        for file_uploader in self.file_uploaders:
            file_uploader.cancel()

    def is_all_files_uploaded(self, jmc_file_id: str):
        self._num_file_uploaded += 1
        self.files_to_analyze.append(jmc_file_id)
        if self._num_file_uploaded == len(self.layer_files) and not self._cancel:
            self._num_file_uploaded = 0
            self.file_uploaders = []
            self.start_poking_jmc_file_analyzers()

    def start_poking_jmc_file_analyzers(self):
        self.step_title_changed.emit(self.tr("Server is analyzing files"))

        def is_file_analyzed(response: RequestManager.ResponseData, jmc_file_id: str):
            if not bool(response.content) or "status" not in response.content or response.content["status"] in ["UPLOADING", "ERROR"]:
                for layer_file in self.layer_files:
                    if layer_file.jmc_file_id == jmc_file_id:
                        layer_file.upload_status = LayerFile.Status.uploading_error
                        break
                self.files_to_analyze.remove(jmc_file_id)
            elif response.content["status"] == "ANALYZED":
                for layer_file in self.layer_files:
                    if layer_file.jmc_file_id == jmc_file_id:
                        if layer_file.file_type != SupportedFileType.raster:
                            for layer in response.content["metadata"]["layers"]:
                                layer_file.fields[layer["name"]] = layer["fileAttributes"]
                        break
                self.files_to_analyze.remove(jmc_file_id)
            if len(self.files_to_analyze) == 0 and not self._cancel:
                self.recurring_event.stop()
                self._num_file_uploaded = 0
                self.tasks_completed.emit(self.layers_data)

        def poke_all_not_analyzed_files():
            if self._cancel:
                self.recurring_event.stop()

            for jmc_file_id in self.files_to_analyze:
                url = "{}/organizations/{}/files/{}".format(API_FUS_URL, self.organization_id, jmc_file_id)
                request = RequestManager.RequestData(url, type="GET", id=jmc_file_id)
                next_func = lambda response, _jmc_file_id=jmc_file_id: is_file_analyzed(response, _jmc_file_id)
                self.request_manager.add_requests(request).connect(next_func)

        self.recurring_event = RecurringEvent(2.5, poke_all_not_analyzed_files, False, 200)
        self.recurring_event.call_count_exceeded.connect(self.timeout)
        self.recurring_event.start()

    def timeout(self):
        pass


class FileUploader(CustomTaskManager):
    """
    Send a list of requests and wait for all responses.
    This class is used to upload a file in chunks.
    Multiple instances of this class will upload multiple files in parallel.
    :tasks_completed: signal emit when all requests are finished
    """

    tasks_completed = pyqtSignal(str)
    """returns jmc_file_id"""

    def __init__(self, layer_file: LayerFile, organization_id: str):
        super().__init__("FileUploader")
        self.layer_file: LayerFile = layer_file
        self.organization_id: str = organization_id

        self.file_path = Path(layer_file.file_path)
        self.file_length: int = Path(layer_file.file_path).stat().st_size
        self.file_offset: int = 0
        self.url: str = None

        self.request = None
        self.responses: list[RequestManager.ResponseData] = []
        self.pending_requests: list[RequestManager.RequestData] = []
        self.upload_safer_counter: int = 0
        self.step: int = 0
        self.total_steps: int = math.ceil(self.file_length / CHUNK_SIZE) + 1
        self._cancel: bool = False
        self.request_manager = RequestManager.instance()

    def run(self):
        self.init_upload()

    def init_upload(self) -> None:
        if self._cancel:
            return False
        file_name64 = base64.b64encode(self.file_path.name.encode("utf-8")).decode("utf-8")
        if self.layer_file.file_type == SupportedFileType.raster:
            file_type64 = base64.b64encode("image/tiff".encode("utf-8")).decode("utf-8")
            jmc_file_type64 = base64.b64encode("RASTER_DATA".encode("utf-8")).decode("utf-8")
        else:
            file_type64 = base64.b64encode("application/x-zip-compressed".encode("utf-8")).decode("utf-8")
            jmc_file_type64 = base64.b64encode("VECTOR_DATA".encode("utf-8")).decode("utf-8")

        url = "{}/organizations/{}/upload".format(API_FUS_URL, self.organization_id)
        headers = {
            "Upload-Length": "{}".format(self.file_length),
            "Upload-Metadata": "filename {},filetype {},JMC-fileType {}".format(
                file_name64, file_type64, jmc_file_type64
            ),
            "Tus-Resumable": "1.0.0",
        }
        error_prefix = "Error uploading file"
        response = RequestManager.post_request(url, headers=headers, error_prefix=error_prefix)
        if response.headers is None or response.content is None:
            return False
        location: str = None
        for header, value in response.headers.items():
            if header == "Location":
                location = value
        if not location:
            return False

        url_array = location.split("/")
        file_id = url_array[-1]
        self.layer_file.jmc_file_id = file_id
        self.url = "{}/{}".format(url, file_id)
        self.progress_changed.emit(self.step / self.total_steps * 100.0)
        self.execute_next_request(response)
        return True

    def execute_next_request(self, response: RequestManager.ResponseData = None) -> None:
        """
        this function must be call after upload initialization
        """
        if self._cancel:
            return False
        if response != None:
            if response.status != QNetworkReply.NetworkError.NoError:
                self.upload_safer_counter += 1
                if self.upload_safer_counter >= 5:
                    error_message = "Request failed: {}".format(response.error_message)
                    self.error_occur(error_message, MESSAGE_CATEGORY)
                    self.responses.append(response)
                    self.pending_requests = []
                    self.layer_file.upload_status = LayerFile.Status.uploading_error
                    self.tasks_completed.emit(self.layer_file.jmc_file_id)
                    self.progress_changed.emit(100.0)
                    return False

                def resend_request():
                    response_signal_obj = self.request_manager.add_requests(self.request)
                    response_signal_obj.connect(lambda response, this=self: this.execute_next_request(response))
                    self.pending_requests.append(response_signal_obj)

                QTimer.singleShot(2000, resend_request)
                return False
            else:
                self.upload_safer_counter = 0
                self.responses.append(response)
                self.step += 1  # first call will be on initialization
                self.progress_changed.emit(self.step / self.total_steps * 100.0)
            if self.file_offset >= self.file_length:
                self.pending_requests = []
                self.tasks_completed.emit(self.layer_file.jmc_file_id)
                return True
        self.request = self.define_next_request()
        self.file_offset += CHUNK_SIZE
        response_signal_obj = self.request_manager.add_requests(self.request)
        response_signal_obj.connect(lambda response, this=self: this.execute_next_request(response))
        self.pending_requests.append(response_signal_obj)
        return True

    def define_next_request(self) -> RequestManager.RequestData:
        with open(self.layer_file.file_path, "rb") as f:
            f.seek(self.file_offset)
            chunk = f.read(CHUNK_SIZE)
        length_left = self.file_length - self.file_offset
        content_length = CHUNK_SIZE if CHUNK_SIZE < length_left else length_left
        headers = {
            "content-type": "application/offset+octet-stream",
            "Tus-Resumable": "1.0.0",
            "content-length": "{}".format(content_length),
            "Upload-Offset": "{}".format(self.file_offset),
        }
        return RequestManager.RequestData(
            self.url,
            headers,
            chunk,
            "PATCH",
            self.layer_file.jmc_file_id,
        )

    def cancel(self):
        self._cancel = True


class DatasourceManager(CustomTaskManager):
    tasks_completed = pyqtSignal(list)

    def __init__(self, layers_data: list[LayerData], organization_id: str):
        super().__init__("DatasourceManager")
        self.layers_data = layers_data
        self.organization_id = organization_id
        self._num_datasource_created = 0
        self.datasource_to_analyze: list[LayerData] = []
        self.request_manager = RequestManager.instance()
        self._cancel = False

    def run(self):
        self.create_datasources()

    def cancel(self):
        self._cancel = True

    def create_datasources(self):
        self.step_title_changed.emit(self.tr("Creating datasources"))
        for layer_data in self.layers_data:
            self.create_datasource(layer_data)

    def create_datasource(self, layer_data: LayerData) -> bool:
        # prepare request data
        request_DTO = DatasourceDTO()
        request_DTO.description = ""  # TODO
        request_DTO.tags = []  # TODO
        request_DTO.name = layer_data.layer_name
        request_DTO.type = layer_data.layer_type.value

        if layer_data.layer_type == LayerData.LayerType.file_vector:
            uri_layer_name = layer_data.uri_components["layerName"]
            crs = convert_crs_to_epsg(layer_data.layer.crs())
            request_DTO.crs = crs.authid()

            request_DTO.fileId = layer_data.layer_file.jmc_file_id
            request_DTO.indexedAttributes = []
            # GeoJSON uploads are reported as "defaultLayer" by the server analyzer.
            fields_by_layer = layer_data.layer_file.fields if layer_data.layer_file else {}
            if not uri_layer_name:
                uri_layer_name = "defaultLayer"
            if uri_layer_name not in fields_by_layer:
                if "defaultLayer" in fields_by_layer:
                    uri_layer_name = "defaultLayer"
                elif len(fields_by_layer) > 0:
                    uri_layer_name = next(iter(fields_by_layer))
            request_DTO.layer = uri_layer_name
            request_DTO.layers = [{"id": 0, "name": uri_layer_name}]
            request_DTO.params = {}

            fields = fields_by_layer.get(uri_layer_name, [])
            request_DTO.params["attributes"] = fields
            # for field in fields:
            #    if field.name().lower() == "annotation_height_3857":  # annotation_height_3857 is reserved
            #        continue
            #    request_DTO.params["attributes"].append(
            #        {
            #            "originalName": field.name(),
            #            "standardizedName": field.name(),
            #            "type": qgis_data_type_name_to_mysql(field.type()),
            #        }
            #    )
            if layer_data.file_type in [
                SupportedFileType.GML,
                SupportedFileType.FileGeoDatabase,
                SupportedFileType.GeoPackage,
                SupportedFileType.CAD,
                SupportedFileType.DXF,
                SupportedFileType.KML,
                SupportedFileType.MapInfo,
            ]:
                request_DTO.params["layers"] = [uri_layer_name]
            if layer_data.file_type == SupportedFileType.CSV:
                request_DTO.params["columnX"] = layer_data.longitude
                request_DTO.params["columnY"] = layer_data.latitude

        elif layer_data.layer_type == LayerData.LayerType.file_raster:
            request_DTO.fileId = layer_data.layer_file.jmc_file_id
        elif layer_data.layer_type == LayerData.LayerType.API_FEATURES:
            request_DTO.params = {
                "landingPageUrl": layer_data.datasource["landingPageUrl"],
                "collectionId": layer_data.datasource["collectionId"],
            }
        elif layer_data.layer_type == LayerData.LayerType.WMS_WMTS:
            request_DTO.capabilitiesUrl = layer_data.datasource["capabilitiesUrl"]
        else:
            return False

        # request
        url = "{}/organizations/{}/datasources".format(API_MCS_URL, self.organization_id)
        body = request_DTO.to_json()
        request = RequestManager.RequestData(url, body=body, type="POST", id=layer_data.layer_id)
        response = RequestManager.custom_request(request)
        self.read_datasource_creation_response(response, layer_data)
        return True

    def read_datasource_creation_response(self, response: RequestManager.ResponseData, layer_data: LayerData):
        if response.status == QNetworkReply.NetworkError.NoError and "id" in response.content:
            datasource_id = response.content["id"]
            layer_data.datasource_id = datasource_id
        else:
            layer_data.status = LayerData.Status.creating_datasource_error
            self.error_occur(response.error_message, MESSAGE_CATEGORY)
        self.is_all_datasources_created(layer_data)

    def is_all_datasources_created(self, layer_data: LayerData):
        self._num_datasource_created += 1
        self.progress_changed.emit(self._num_datasource_created / len(self.layers_data) * 100)
        if layer_data.status == LayerData.Status.no_error:
            self.datasource_to_analyze.append(layer_data)
        if self._num_datasource_created == len(self.layers_data):
            self._num_datasource_created = 0
            self.start_poking_jmc_datasource_analyzers()

    def start_poking_jmc_datasource_analyzers(self):
        self.step_title_changed.emit(self.tr("Server is analyzing datasources"))

        def is_datasource_analyzed(response: RequestManager.ResponseData, layer_data: LayerData = None):
            if response.status != QNetworkReply.NetworkError.NoError:
                self.datasource_to_analyze.remove(layer_data)
                layer_data.status = LayerData.Status.unknown_error
                self.error_occur(self.tr("Unknown error : {}").format(response.error_message), MESSAGE_CATEGORY)
            elif "status" not in response.content or response.content["status"] == "ERROR":
                self.datasource_to_analyze.remove(layer_data)
                layer_data.status = LayerData.Status.datasource_analyzing_error
                self.error_occur(self.tr("JMap server error : {}").format(response.error_message), MESSAGE_CATEGORY)
            elif response.content["status"] in ["READY"]:
                self.datasource_to_analyze.remove(layer_data)
                layer_data.datasource_id = response.content["id"]
            if len(self.datasource_to_analyze) == 0:
                recurring_event.stop()
                self.tasks_completed.emit(self.layers_data)

        def poke_all_not_analyzed_datasources():
            for layer_data in self.datasource_to_analyze:
                url = "{}/organizations/{}/datasources/{}".format(
                    API_MCS_URL, self.organization_id, layer_data.datasource_id
                )
                request = RequestManager.RequestData(url, type="GET", id=layer_data.datasource_id)
                next_func = lambda response, layer_data=layer_data: is_datasource_analyzed(response, layer_data)
                self.request_manager.add_requests(request).connect(next_func)
            if len(self.datasource_to_analyze) == 0:
                recurring_event.stop()
                self.tasks_completed.emit(self.layers_data)

        recurring_event = RecurringEvent(2.5, poke_all_not_analyzed_datasources, False, 200)
        recurring_event.call_count_exceeded.connect(self.timeout)
        recurring_event.start()

    def timeout(self):
        pass
