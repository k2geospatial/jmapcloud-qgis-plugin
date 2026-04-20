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

import urllib.parse
import zipfile
from pathlib import Path
from typing import Union

from qgis.core import (
    QgsApplication,
    QgsMapLayer,
    QgsProviderRegistry,
    QgsRasterFileWriter,
    QgsRasterFileWriterTask,
    QgsRasterLayer,
    QgsRasterPipe,
    QgsTask,
    QgsVectorFileWriter,
    QgsVectorFileWriterTask,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import pyqtSignal

from ..views import LayerData, LayerFile, SupportedFileType
from .custom_qgs_task import CustomQgsTask, CustomTaskManager

MESSAGE_CATEGORY = "WriteLayerTask"


class ConvertLayersToZipTask(CustomTaskManager):
    tasks_completed = pyqtSignal(list, list)

    def __init__(self, dir_path, layers: list[QgsMapLayer]):
        super().__init__("ConvertLayersToZipTask")
        self.dir_path = dir_path
        self.layers = layers
        self.layers_data: list[LayerData] = []
        self.layer_files: list[LayerFile] = []
        self._layer_tasks: list["ConvertLayerToZipTask"] = []
        self._completed_count = 0
        self._progress_by_layer: list[float] = [0.0] * len(layers)

    def run(self) -> bool:
        if self.is_canceled():
            return False

        if len(self.layers) == 0:
            self.progress_changed.emit(100.0)
            self.tasks_completed.emit(self.layers_data, self.layer_files)
            return True

        for index, layer in enumerate(self.layers):
            layer_task = ConvertLayerToZipTask(self.dir_path, layer)
            self._layer_tasks.append(layer_task)

            def on_progress(value: float, ref=index):
                self._progress_by_layer[ref] = value
                total_progress = sum(self._progress_by_layer) / len(self._progress_by_layer)
                self.progress_changed.emit(total_progress)

            def on_completed(layer_data: LayerData, layer_file: Union[LayerFile, None]):
                if layer_data is not None:
                    self.layers_data.append(layer_data)
                    if layer_file is not None:
                        self._register_layer_file(layer_file)
                self._completed_count += 1
                if self._completed_count == len(self.layers):
                    self.progress_changed.emit(100.0)
                    self.tasks_completed.emit(self.layers_data, self.layer_files)

            layer_task.progress_changed.connect(on_progress)
            layer_task.error_occurred.connect(self.error_occurred.emit)
            layer_task.tasks_completed.connect(on_completed)
            layer_task.run()
        return True

    def cancel(self):
        super().cancel()
        for layer_task in self._layer_tasks:
            layer_task.cancel()

    def _register_layer_file(self, layer_file: LayerFile):
        if all(existing.file_path != layer_file.file_path for existing in self.layer_files):
            self.layer_files.append(layer_file)


class ConvertLayerToZipTask(CustomTaskManager):
    tasks_completed = pyqtSignal(object, object)  # layer_data, layer_file

    def __init__(self, dir_path: str, layer: QgsMapLayer):
        super().__init__("ConvertLayerToZipTask")
        self.dir_path = dir_path
        self.layer = layer
        self.layer_data: Union[LayerData, None] = None
        self.layer_file: Union[LayerFile, None] = None
        self._tasks: list[QgsTask] = []
        self._total_tasks = 0

    def run(self) -> bool:
        if self.is_canceled():
            return False

        if not isinstance(self.layer, (QgsRasterLayer, QgsVectorLayer)):
            message = self.tr("Layer {} of type {} is not supported for export").format(
                self.layer.name(), type(self.layer)
            )
            self.error_occur(message, MESSAGE_CATEGORY)
            self.tasks_completed.emit(None, None)
            return False

        self.layer_data = LayerData(
            layer=self.layer, layer_id=self.layer.id(), layer_name=self.layer.name()
        )
        if isinstance(self.layer, QgsVectorLayer):
            self.layer_data.element_type = self.layer.geometryType().name.upper()

        sources = self.get_layer_source(self.layer_data)

        def on_convert_error(message: str = None):
            if self.layer_data:
                self.layer_data.status = LayerData.Status.file_compressing_error
                self.layer_data.layer_file = None
            error_message = self.tr("Error writing layer for layer {}: {}").format(
                self.layer_data.layer_name if self.layer_data else "unknown",
                message or "",
            )
            self.error_occur(error_message, MESSAGE_CATEGORY)

        if not sources:
            if self.layer_data.layer_type == LayerData.LayerType.file_vector:
                sources = [Path(self.dir_path, "{}.geojson".format(self.layer_data.layer_name))]
                output_path = Path(self.dir_path, "{}.zip".format(self.layer_data.layer_name))
                self.layer_file = LayerFile(
                    file_path=str(output_path),
                    file_name=self.layer_data.layer_name,
                    file_type=self.layer_data.file_type,
                )
                self.layer_data.layer_file = self.layer_file

                write_subtask = CustomWriteVectorLayerTask(sources[0], self.layer_data.layer)
                compress_task = compressFilesToZipTask(sources, output_path)
                compress_task.addSubTask(
                    write_subtask,
                    subTaskDependency=QgsTask.SubTaskDependency.ParentDependsOnSubTask,
                )
                write_subtask.error_occurred.connect(on_convert_error)
                compress_task.error_occurred.connect(on_convert_error)
                compress_task.taskCompleted.connect(
                    lambda task=compress_task: self._on_sub_task_finished(task)
                )
                compress_task.taskTerminated.connect(
                    lambda task=compress_task: self._on_sub_task_finished(task)
                )
                self._tasks.append(compress_task)
                self._total_tasks += 1

            elif self.layer_data.layer_type == LayerData.LayerType.file_raster:
                sources = [Path(self.dir_path, "{}.tiff".format(self.layer_data.layer_name))]
                self.layer_file = LayerFile(
                    file_path=str(sources[0]),
                    file_name=self.layer.name(),
                    file_type=self.layer_data.file_type,
                )
                self.layer_data.layer_file = self.layer_file

                write_task = CustomWriteRasterLayerTask(sources[0], self.layer_data.layer)
                write_task.error_occurred.connect(on_convert_error)
                write_task.taskCompleted.connect(
                    lambda task=write_task: self._on_sub_task_finished(task)
                )
                write_task.taskTerminated.connect(
                    lambda task=write_task: self._on_sub_task_finished(task)
                )
                self._tasks.append(write_task)
                self._total_tasks += 1
            else:
                message = self.tr("Error writing layer '{}': unknown layer type").format(
                    self.layer_data.layer_name
                )
                self.error_occur(message, MESSAGE_CATEGORY)
                self.layer_data.status = LayerData.Status.file_creation_error
                self.tasks_completed.emit(self.layer_data, None)
                return False

        elif isinstance(sources, dict):
            self.layer_data.datasource = sources
        elif all(isinstance(source, Path) for source in sources):
            if self.layer_data.layer_type == LayerData.LayerType.file_vector:
                if self.layer_data.file_type == SupportedFileType.zip:
                    output_path = sources[0]
                else:
                    output_path = Path(self.dir_path, "{}.zip".format(sources[0].stem))

                self.layer_file = LayerFile(
                    file_path=str(output_path),
                    file_name=sources[0].stem,
                    file_type=self.layer_data.file_type,
                )
                self.layer_data.layer_file = self.layer_file

                if self.layer_data.file_type != SupportedFileType.zip:
                    compress_task = compressFilesToZipTask(sources, output_path)
                    compress_task.error_occurred.connect(on_convert_error)
                    compress_task.taskCompleted.connect(
                        lambda task=compress_task: self._on_sub_task_finished(task)
                    )
                    compress_task.taskTerminated.connect(
                        lambda task=compress_task: self._on_sub_task_finished(task)
                    )
                    self._tasks.append(compress_task)
                    self._total_tasks += 1

            elif self.layer_data.layer_type == LayerData.LayerType.file_raster:
                if self.layer_data.file_type == SupportedFileType.zip:
                    message = self.tr("Error writing layer {}: zip raster not supported").format(
                        self.layer_data.layer_name
                    )
                    self.error_occur(message, MESSAGE_CATEGORY)
                    self.layer_data.status = LayerData.Status.file_creation_error
                    self.tasks_completed.emit(self.layer_data, None)
                    return False

                output_path = Path(sources[0])
                self.layer_file = LayerFile(
                    file_path=str(output_path),
                    file_name=sources[0].stem,
                    file_type=self.layer_data.file_type,
                )
                self.layer_data.layer_file = self.layer_file

        if len(self._tasks) == 0:
            self.progress_changed.emit(100.0)
            self.tasks_completed.emit(self.layer_data, self.layer_file)
        else:
            for task in self._tasks:
                QgsApplication.taskManager().addTask(task)
        return True

    def _on_sub_task_finished(self, task: QgsTask):
        if self.is_canceled():
            return
        if task in self._tasks:
            self._tasks.remove(task)
        if self._total_tasks > 0:
            self.progress_changed.emit(
                (self._total_tasks - len(self._tasks)) / self._total_tasks * 100.0
            )
        if len(self._tasks) == 0:
            self.tasks_completed.emit(self.layer_data, self.layer_file)

    def cancel(self):
        super().cancel()
        for task in self._tasks:
            task.cancel()

    def get_layer_source(self, layer_data: LayerData) -> Union[list, dict, None]:
        """
        Retrieve all files or sources associated with a QGIS layer,
        ensuring required files exist.
        """
        layer = layer_data.layer
        if not layer:
            return None

        provider_name = layer.dataProvider().name().lower()
        uri_components = QgsProviderRegistry.instance().decodeUri(
            provider_name, layer.publicSource()
        )
        layer_data.uri_components = uri_components

        if layer_data.uri_components.get("layerName") is None:
            layer_data.uri_components["layerName"] = "defaultLayer"

        # if "layerName" in uri_components and uri_components["layerName"] != None:
        #    layer_data.layer_name = uri_components["layerName"]
        # else:
        #    layer_data.layer_name = layer.name()

        # ---- API-based layers (WFS-like) ----
        if provider_name in ["oapif", "wfs"]:
            layer_data.layer_type = LayerData.LayerType.API_FEATURES
            uri = layer.dataProvider().uri()
            url = uri.param("url")
            collectionId = uri.param("typename")
            return {"landingPageUrl": url, "collectionId": collectionId}

        # --- Database vector layers ---
        # TODO check other DB providers
        elif (
            isinstance(layer, QgsVectorLayer)
            and layer.isSpatial()
            and provider_name in ["spatialite", "postgres", "mysql", "oracle", "mssql"]
        ):
            # Any spatial vector provider that comes from a database, export to GeoJSON
            layer_data.layer_type = LayerData.LayerType.file_vector
            layer_data.file_type = SupportedFileType.GeoJSON
            layer_data.uri_components["layerName"] = "defaultLayer"
            return None

        # ---- File-based vector layers ----
        elif isinstance(layer, QgsVectorLayer) and layer.isSpatial() and "path" in uri_components:
            layer_data.layer_type = LayerData.LayerType.file_vector
            base_path = Path(uri_components["path"])
            storage_type = layer.dataProvider().storageType()
            ext = base_path.suffix.lower()
            if (
                base_path.is_dir()
                and ext not in [".gdb", "mdb"]
                and "layerName" in uri_components
                and bool(uri_components["layerName"])
            ):
                base_path = base_path / uri_components["layerName"]
                ext = base_path.suffix.lower()
            # --- Zip file ---
            if base_path.suffix.lower() == ".zip":
                layer_data.file_type = SupportedFileType.zip
                return [Path(base_path)] if base_path.exists() else None
            # --- ESRI Shapefile (requires multiple files) ---
            if storage_type == "ESRI Shapefile":
                layer_data.uri_components["layerName"] = base_path.stem

                required_files = [".shp", ".shx", ".dbf"]
                optional_files = [".prj", ".cpg", ".qpj", ".fix"]
                all_files = required_files + optional_files

                missing_files = [e for e in required_files if not base_path.with_suffix(e).exists()]
                if missing_files:
                    message = self.tr("Missing required files for {}: {}").format(
                        base_path.name, missing_files
                    )
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return None
                layer_data.file_type = SupportedFileType.SHP
                return [
                    Path(base_path.with_suffix(e))
                    for e in all_files
                    if base_path.with_suffix(e).exists()
                ]
            # --- MapInfo TAB (requires all files) ---
            elif storage_type == "MapInfo File":
                layer_data.uri_components["layerName"] = base_path.stem

                if base_path.with_suffix(".mid").exists() or base_path.with_suffix(".mif").exists():
                    message = self.tr("Unsupported file type .mid/.mif for layer {}").format(
                        layer_data.layer_name
                    )
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return None

                required_files = [".tab", ".dat", ".map", ".id"]
                missing_files = [e for e in required_files if not base_path.with_suffix(e).exists()]
                if missing_files:
                    message = self.tr("Missing required files for {}: {}").format(
                        base_path.name, missing_files
                    )
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return None
                layer_data.file_type = SupportedFileType.MapInfo
                return [Path(base_path.with_suffix(e)) for e in required_files]
            # --- Single-file formats ---
            elif storage_type == "GeoJSON":
                layer_data.uri_components["layerName"] = "defaultLayer"

                if base_path.suffix.lower() not in [".geojson", ".json"]:
                    message = self.tr("Unsupported file type {} for layer {}").format(
                        base_path.suffix.lower(), layer_data.layer_name
                    )
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return None
                layer_data.file_type = SupportedFileType.GeoJSON
                return [Path(base_path)] if base_path.exists() else None
            elif storage_type == "Delimited text file":
                supported_file_extensions = [".csv", ".txt"]

                if base_path.suffix.lower() not in supported_file_extensions:
                    message = self.tr("Unsupported file type {} for layer {}").format(
                        base_path.suffix.lower(), layer_data.layer_name
                    )
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return None

                open_options: Union[list, None] = (
                    uri_components["openOptions"] if "openOptions" in uri_components else None
                )
                xField = None
                yField = None
                if open_options:
                    for option in open_options:
                        if "=" not in option:
                            continue
                        key, value = option.split("=", 1)
                        decoded_value = urllib.parse.unquote_plus(value)
                        lowered_key = key.lower()
                        if lowered_key == "xfield":
                            xField = decoded_value
                        elif lowered_key == "yfield":
                            yField = decoded_value

                # Some providers may expose x/y field names directly in decoded URI components.
                if not xField and "xField" in uri_components:
                    xField = uri_components["xField"]
                if not yField and "yField" in uri_components:
                    yField = uri_components["yField"]

                layer_data.longitude = xField
                layer_data.latitude = yField
                layer_data.file_type = SupportedFileType.CSV

                if not (layer_data.longitude and layer_data.latitude):
                    return None
                return [Path(base_path)] if base_path.exists() else None
            elif storage_type == "GML":
                if base_path.suffix.lower() != ".gml":
                    message = self.tr("Unsupported file type {} for layer {}").format(
                        base_path.suffix.lower(), layer_data.layer_name
                    )
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return None

                layer_data.file_type = SupportedFileType.GML
                return [Path(base_path)] if base_path.exists() else None
            elif storage_type == "GPKG":
                layer_data.file_type = SupportedFileType.GeoPackage

                return [Path(base_path)] if base_path.exists() else None
            elif storage_type == "LIBKML":
                layer_data.file_type = SupportedFileType.KML
                return [Path(base_path)] if base_path.exists() else None
            elif storage_type == "OpenFileGDB":  # FileGeoDatabase
                layer_data.file_type = SupportedFileType.FileGeoDatabase
                return [Path(base_path)] if base_path.exists() else None
            elif storage_type == "DXF":  # CAD files
                layer_data.file_type = SupportedFileType.CAD
                return [Path(base_path)] if base_path.exists() else None
            else:
                message = self.tr("Unsupported file type {} for layer {}").format(
                    ext, layer_data.layer_name
                )
                self.error_occur(message, MESSAGE_CATEGORY)
                return None

        # ---- WMS / WMTS ----
        elif provider_name in ["wms", "wmts"] and "url" in uri_components:
            layer_data.layer_type = LayerData.LayerType.WMS_WMTS
            return {"capabilitiesUrl": self._build_wms_capabilities_url(uri_components["url"])}

        # ---- File-based Raster layers ----
        elif isinstance(layer, QgsRasterLayer) and "path" in uri_components:
            layer_data.layer_type = LayerData.LayerType.file_raster

            base_path = Path(uri_components["path"])
            ext = base_path.suffix.lower()
            # not supported now
            # extensions = [
            # ".tif",
            # ".tiff",
            # ".jp2",
            # ".ecw",
            # ".sid",
            # ".img",
            # ".vrt",
            # ".asc"]
            extensions = [".tif", ".tiff"]

            if ext in extensions:
                layer_data.file_type = SupportedFileType.raster
                return [Path(base_path)] if base_path.exists() else None
            elif ext == ".zip":
                layer_data.file_type = SupportedFileType.zip
                return [Path(base_path)] if base_path.exists() else None
            else:
                message = self.tr("Unsupported file type {} for layer {}").format(
                    ext, layer_data.layer_name
                )
                self.error_occur(message, MESSAGE_CATEGORY)
                return None

        # ---- Unsupported layers ----
        message = self.tr("Unsupported layer: {} ({}), the provider is not supported").format(
            layer_data.layer_name, provider_name
        )
        self.error_occur(message, MESSAGE_CATEGORY)
        return None

    def _build_wms_capabilities_url(self, raw_url: str) -> str:
        decoded_url = urllib.parse.unquote_plus(raw_url or "").strip()
        parsed_url = urllib.parse.urlsplit(decoded_url)
        query_items = [
            (key, value)
            for key, value in urllib.parse.parse_qsl(parsed_url.query, keep_blank_values=True)
            if key.lower() not in {"service", "request"}
        ]
        query_items.append(("SERVICE", "WMS"))
        query_items.append(("REQUEST", "GetCapabilities"))
        query = urllib.parse.urlencode(query_items, doseq=True)
        return urllib.parse.urlunsplit(
            (parsed_url.scheme, parsed_url.netloc, parsed_url.path, query, parsed_url.fragment)
        )


class CustomWriteVectorLayerTask(CustomQgsTask):

    def __init__(self, output_path: Path, layer: QgsVectorLayer):
        super().__init__("Write Vector Layer", QgsTask.Flag.CanCancel)
        writer_options = QgsVectorFileWriter.SaveVectorOptions()
        writer_options.driverName = "GeoJSON"
        writer_options.layerName = layer.name()
        writer_options.forceMulti = False
        writer_options.includeZ = False
        writer_options.attributes = layer.fields().allAttributesList()

        self.main_task = QgsVectorFileWriterTask(layer, str(output_path), writer_options)
        self.main_task.errorOccurred.connect(
            lambda _, error_message: self.error_occur(error_message, MESSAGE_CATEGORY)
        )
        self.addSubTask(
            self.main_task, subTaskDependency=self.SubTaskDependency.ParentDependsOnSubTask
        )

    def run(self):
        if self.isCanceled():
            return False
        return True


class CustomWriteRasterLayerTask(CustomQgsTask):
    write_layer_completed: pyqtSignal = pyqtSignal()

    def __init__(self, output_path: Path, layer: QgsRasterLayer):
        super().__init__("Write raster Layer", QgsTask.Flag.CanCancel)
        file_writer = QgsRasterFileWriter(str(output_path))
        pipe = QgsRasterPipe()
        provider = layer.dataProvider()

        if not pipe.set(provider):
            self.error_occur("Cannot set pipe provider", MESSAGE_CATEGORY)

        self.main_task = QgsRasterFileWriterTask(
            file_writer, pipe, layer.width(), layer.height(), provider.extent(), provider.crs()
        )
        self.main_task.errorOccurred.connect(
            lambda _, error_message: self.error_occur(error_message, MESSAGE_CATEGORY)
        )
        self.main_task.writeComplete.connect(self.write_layer_completed)
        self.addSubTask(
            self.main_task, subTaskDependency=self.SubTaskDependency.ParentDependsOnSubTask
        )


class compressFilesToZipTask(CustomQgsTask):

    def __init__(self, files_path: list[Path], output_path: Path):
        super().__init__("Compress Layer", QgsTask.Flag.CanCancel)
        self.files_path = files_path
        self.output_path = output_path
        self.tr("Converting layers to zip")

    def run(self) -> bool:
        if self.isCanceled():
            return False
        try:
            # compress file
            with zipfile.ZipFile(self.output_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
                self.set_total_steps(len(self.files_path))
                for input_path in self.files_path:
                    if self.isCanceled():
                        return False
                    if input_path.is_file():
                        zip_file.write(input_path, arcname=input_path.name)

                    elif input_path.is_dir():
                        for file_path in input_path.rglob("*"):  # Replaces os.walk()
                            if file_path.is_file():  # Ensure only files are added
                                arcname = file_path.relative_to(input_path)  # Preserve structure
                                zip_file.write(file_path, arcname=arcname)
                    else:
                        message = self.tr("Error: {} is not a valid file or folder.").format(
                            input_path
                        )
                        raise Exception(message)
                    self.next_steps()

        except Exception as e:
            self.exceptions.append(e)
            self.error_occur(str(e), MESSAGE_CATEGORY)
            self.setProgress(100)
            return False
        return True
