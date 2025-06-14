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

from .custom_qgs_task import CustomQgsTask, CustomTaskManager
from ..views import LayerData, LayerFile, SupportedFileType

MESSAGE_CATEGORY = "WriteLayerTask"


class ConvertLayersToZipTask(CustomTaskManager):
    tasks_completed = pyqtSignal((list, list))

    def __init__(self, dir_path, layers: list[QgsMapLayer]):
        super().__init__("ConvertLayersToZipTask")
        self.dir_path = dir_path
        self.layers = layers
        self.layers_data: list[LayerData] = []
        self.layer_files: list[LayerFile] = []
        self.exception: str = None
        self.total_tasks = 0

    def run(self) -> bool:
        if self.is_canceled():
            return False
        for layer in self.layers:
            if not isinstance(layer, QgsRasterLayer) and not isinstance(layer, QgsVectorLayer):
                message = self.tr("Layer {} of type {} is not supported for export").format(layer.name(), type(layer))
                self.error_occur(message, MESSAGE_CATEGORY)
                continue
            layer_data = LayerData(layer=layer, layer_id=layer.id(), layer_name=layer.name())
            if isinstance(layer, QgsVectorLayer):
                layer_data.element_type = layer.geometryType().name.upper()
            sources = self.get_layer_source(layer_data)

            def on_convert_error(message: str = None, layer_data=layer_data):
                layer_data.status = LayerData.Status.file_compressing_error
                self.layer_files.remove(layer_data.layer_file)
                layer_data.layer_file = None

                layer_data.status = LayerData.Status.file_compressing_error
                message = self.tr("Error writing layer for layer {}: {}").format(layer_data.layer_name, message or "")
                self.error_occur(message, MESSAGE_CATEGORY)

            if not sources:  # create a geojson file and write it to zip
                if layer_data.layer_type == LayerData.LayerType.file_vector:
                    sources = [Path(self.dir_path, "{}.geojson".format(layer_data.layer_name))]
                    output_path = Path(self.dir_path, "{}.zip".format(layer_data.layer_name))
                    layer_data.layer_file = LayerFile(
                        file_path=str(output_path), file_name=layer_data.layer_name, file_type=layer_data.file_type
                    )
                    self.layer_files.append(layer_data.layer_file)

                    # create subtasks
                    write_subtask = CustomWriteVectorLayerTask(sources[0], layer_data.layer)
                    compress_task = compressFilesToZipTask(sources, output_path)
                    compress_task.addSubTask(
                        write_subtask, subTaskDependency=QgsTask.SubTaskDependency.ParentDependsOnSubTask
                    )
                    write_subtask.error_occurred.connect(on_convert_error)
                    compress_task.error_occurred.connect(on_convert_error)
                    compress_task.taskCompleted.connect(lambda task=compress_task: self.all_sub_tasks_finished(task))
                    compress_task.taskTerminated.connect(lambda task=compress_task: self.all_sub_tasks_finished(task))
                    # set tasks order
                    self.tasks.append(compress_task)
                    self.total_tasks += 1
                elif layer_data.layer_type == LayerData.LayerType.file_raster:
                    sources = [Path(self.dir_path, "{}.tiff".format(layer_data.layer_name))]
                    layer_data.layer_file = LayerFile(
                        file_path=str(sources[0]), file_name=layer.name(), file_type=layer_data.file_type
                    )
                    self.layer_files.append(layer_data.layer_file)

                    write_task = CustomWriteRasterLayerTask(sources[0], layer_data.layer)
                    write_task.error_occurred.connect(on_convert_error)
                    write_task.taskCompleted.connect(lambda task=write_task: self.all_sub_tasks_finished(task))
                    write_task.taskTerminated.connect(lambda task=write_task: self.all_sub_tasks_finished(task))
                    # set tasks order
                    self.tasks.append(write_task)
                    self.total_tasks += 1
                else:
                    message = self.tr("Error writing layer '{}': unknown layer type").format(layer_data.layer_name)
                    self.error_occur(message, MESSAGE_CATEGORY)
                    layer_data.status = LayerData.Status.file_creation_error
                    continue

            elif isinstance(sources, dict):  # don't create file because external provider
                layer_data.datasource = sources
            elif all(isinstance(source, Path) for source in sources):
                if layer_data.layer_type == LayerData.LayerType.file_vector:  # compress file to zip
                    if layer_data.file_type == SupportedFileType.zip:
                        output_path = sources[0]
                    else:
                        output_path = Path(self.dir_path, "{}.zip".format(sources[0].stem))
                    for layer_file in self.layer_files:
                        if layer_file.file_path == str(output_path):
                            layer_data.layer_file = layer_file
                            break
                    if not layer_data.layer_file:
                        layer_data.layer_file = LayerFile(
                            file_path=str(output_path), file_name=sources[0].stem, file_type=layer_data.file_type
                        )
                        self.layer_files.append(layer_data.layer_file)

                        if not layer_data.file_type == SupportedFileType.zip:
                            compress_task = compressFilesToZipTask(sources, output_path)
                            compress_task.error_occurred.connect(on_convert_error)
                            compress_task.taskCompleted.connect(
                                lambda task=compress_task: self.all_sub_tasks_finished(task)
                            )
                            compress_task.taskTerminated.connect(
                                lambda task=compress_task: self.all_sub_tasks_finished(task)
                            )
                            self.tasks.append(compress_task)
                            self.total_tasks += 1

                elif layer_data.layer_type == LayerData.LayerType.file_raster:

                    if layer_data.file_type == SupportedFileType.zip:
                        message = self.tr("Error writing layer {}: zip raster not supported").format(
                            layer_data.layer_name
                        )
                        self.error_occur(message, MESSAGE_CATEGORY)
                        continue

                    output_path = Path(sources[0])

                    for layer_file in self.layer_files:
                        if layer_file.file_path == str(output_path):
                            layer_data.layer_file = layer_file
                            break
                    if not layer_data.layer_file:
                        layer_data.layer_file = LayerFile(
                            file_path=str(output_path), file_name=sources[0].stem, file_type=layer_data.file_type
                        )
                        self.layer_files.append(layer_data.layer_file)
            self.layers_data.append(layer_data)
        if len(self.tasks) == 0:
            self.progress_changed.emit(100)
            self.tasks_completed.emit(self.layers_data, self.layer_files)
        else:
            for task in self.tasks:
                QgsApplication.taskManager().addTask(task)
        return True

    def all_sub_tasks_finished(self, task: CustomQgsTask) -> bool:
        if self.is_canceled():
            return False
        self.tasks.remove(task)
        self.progress_changed.emit((self.total_tasks - len(self.tasks)) / self.total_tasks * 100)
        if len(self.tasks) == 0:
            self.tasks_completed.emit(self.layers_data, self.layer_files)

    def get_layer_source(self, layer_data: LayerData) -> list:
        """Retrieve all files or sources associated with a QGIS layer, ensuring required files exist."""
        layer = layer_data.layer
        if not layer:
            return None

        provider_name = layer.dataProvider().name().lower()
        uri_components = QgsProviderRegistry.instance().decodeUri(provider_name, layer.publicSource())
        layer_data.uri_components = uri_components
        if "layerName" not in layer_data.uri_components or layer_data.uri_components["layerName"] == None:
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

        # ---- File-based vector layers ----
        elif isinstance(layer, QgsVectorLayer) and "path" in uri_components:
            layer_data.layer_type = LayerData.LayerType.file_vector
            base_path = Path(uri_components["path"])

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
            if ext == ".zip":
                layer_data.file_type = SupportedFileType.zip
                return [Path(base_path)] if base_path.exists() else None
            # --- ESRI Shapefile (requires multiple files) ---
            if ext == ".shp":
                layer_data.uri_components["layerName"] = base_path.stem

                required_files = [".shp", ".shx", ".dbf"]
                optional_files = [".prj", ".cpg", ".qpj", ".fix"]
                all_files = required_files + optional_files

                missing_files = [e for e in required_files if not base_path.with_suffix(e).exists()]
                if missing_files:
                    message = self.tr("Missing required files for {}: {}").format(base_path.name, missing_files)
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return None
                layer_data.file_type = SupportedFileType.SHP
                return [Path(base_path.with_suffix(e)) for e in all_files if base_path.with_suffix(e).exists()]
            # --- MapInfo TAB (requires all files) ---
            elif ext == ".tab":
                layer_data.uri_components["layerName"] = base_path.stem
                required_files = [".tab", ".dat", ".map", ".id"]
                missing_files = [e for e in required_files if not base_path.with_suffix(e).exists()]
                if missing_files:
                    message = self.tr("Missing required files for {}: {}").format(base_path.name, missing_files)
                    self.error_occur(message, MESSAGE_CATEGORY)
                    return None
                layer_data.file_type = SupportedFileType.MapInfo
                return [Path(base_path.with_suffix(e)) for e in required_files]
            # --- Single-file formats ---
            elif ext == ".geojson":
                layer_data.uri_components["layerName"] = "defaultLayer"
                layer_data.file_type = SupportedFileType.GeoJSON
                return [Path(base_path)] if base_path.exists() else None
            elif ext == ".csv":
                layer_data.longitude = None
                layer_data.latitude = None
                layer_data.file_type = SupportedFileType.CSV

                fields = layer_data.layer.fields().toList()
                for field in fields:
                    if field.name().capitalize() == "Longitude":
                        layer_data.longitude = field.name()
                    elif field.name().capitalize() == "Latitude":
                        layer_data.latitude = field.name()

                if not (layer_data.longitude and layer_data.latitude):
                    # list = [f.name().capitalize() for f in fields if f.typeName() in ["Double", "Real"]]
                    # if len(list) >= 2: # TODO
                    #    return None
                    # else:
                    return None

                return [Path(base_path)] if base_path.exists() else None
            elif ext == ".gml":
                layer_data.file_type = SupportedFileType.GML
                return [Path(base_path)] if base_path.exists() else None
            elif ext == ".gpkg":
                layer_data.file_type = SupportedFileType.GeoPackage
                return [Path(base_path)] if base_path.exists() else None
            elif ext == ".kml":
                layer_data.file_type = SupportedFileType.KML
                return [Path(base_path)] if base_path.exists() else None
            elif ext in [".mdb", ".gdb"]:  # FileGeoDatabase
                layer_data.file_type = SupportedFileType.FileGeoDatabase
                return [Path(base_path)] if base_path.exists() else None
            elif ext in [".dwg", ".dxf"]:  # CAD files
                layer_data.file_type = SupportedFileType.CAD
                return [Path(base_path)] if base_path.exists() else None
            else:
                message = self.tr("Unsupported file type {} for layer {}").format(ext, layer_data.layer_name)
                self.error_occur(message, MESSAGE_CATEGORY)
                return None

        # ---- WMS / WMTS ----
        elif provider_name in ["wms", "wmts"] and "url" in uri_components:
            layer_data.layer_type = LayerData.LayerType.WMS_WMTS
            return {
                "capabilitiesUrl": "{}&SERVICE=WMS&REQUEST=GetCapabilities".format(
                    urllib.parse.unquote_plus(uri_components["url"])
                )
            }

        # ---- File-based Raster layers ----
        elif isinstance(layer, QgsRasterLayer) and "path" in uri_components:
            layer_data.layer_type = LayerData.LayerType.file_raster

            base_path = Path(uri_components["path"])
            ext = base_path.suffix.lower()
            # extensions = [".tif", ".tiff", ".jp2", ".ecw", ".sid", ".img", ".vrt", ".asc"] not supported now
            extensions = [".tif", ".tiff"]

            if ext in extensions:
                layer_data.file_type = SupportedFileType.raster
                return [Path(base_path)] if base_path.exists() else None
            elif ext == ".zip":
                layer_data.file_type = SupportedFileType.zip
                return [Path(base_path)] if base_path.exists() else None
            else:
                message = self.tr("Unsupported file type {} for layer {}").format(ext, layer_data.layer_name)
                self.error_occur(message, MESSAGE_CATEGORY)
                return None

        # ---- Unsupported layers ----
        message = self.tr("Unsupported layer: {} ({}), the provider is not supported").format(
            layer_data.layer_name, provider_name
        )
        self.error_occur(message, MESSAGE_CATEGORY)
        return None


class CustomWriteVectorLayerTask(CustomQgsTask):

    def __init__(self, output_path: Path, layer: QgsVectorLayer):
        super().__init__("Write Vector Layer", QgsTask.CanCancel)
        writer_options = QgsVectorFileWriter.SaveVectorOptions()
        writer_options.driverName = "GeoJSON"
        writer_options.layerName = layer.name()
        writer_options.forceMulti = False
        writer_options.includeZ = False
        writer_options.attributes = layer.fields().allAttributesList()

        self.main_task = QgsVectorFileWriterTask(layer, str(output_path), writer_options)
        self.main_task.errorOccurred.connect(lambda _, error_message: self.error_occur(error_message, MESSAGE_CATEGORY))
        self.addSubTask(self.main_task, subTaskDependency=self.SubTaskDependency.ParentDependsOnSubTask)

    def run(self):
        if self.isCanceled():
            return False
        return True


class CustomWriteRasterLayerTask(CustomQgsTask):
    write_layer_completed: pyqtSignal = pyqtSignal()

    def __init__(self, output_path: Path, layer: QgsRasterLayer):
        super().__init__("Write raster Layer", QgsTask.CanCancel)
        file_writer = QgsRasterFileWriter(str(output_path))
        pipe = QgsRasterPipe()
        provider = layer.dataProvider()

        if not pipe.set(provider):
            self.error_occur("Cannot set pipe provider", MESSAGE_CATEGORY)

        self.main_task = QgsRasterFileWriterTask(
            file_writer, pipe, layer.width(), layer.height(), provider.extent(), provider.crs()
        )
        self.main_task.errorOccurred.connect(lambda _, error_message: self.error_occur(error_message, MESSAGE_CATEGORY))
        self.main_task.writeComplete.connect(self.write_layer_completed)
        self.addSubTask(self.main_task, subTaskDependency=self.SubTaskDependency.ParentDependsOnSubTask)


class compressFilesToZipTask(CustomQgsTask):

    def __init__(self, files_path: list[Path], output_path: Path):
        super().__init__("Compress Layer", QgsTask.CanCancel)
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
                        message = self.tr("Error: {} is not a valid file or folder.").format(input_path)
                        raise Exception(message)
                    self.next_steps()

        except Exception as e:
            self.exceptions.append(e)
            self.error_occur(str(e), MESSAGE_CATEGORY)
            self.setProgress(100)
            return False
        return True
