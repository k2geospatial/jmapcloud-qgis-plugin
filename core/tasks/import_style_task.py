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

from qgis.core import QgsTask, QgsVectorTileBasicRenderer
from qgis.PyQt.QtCore import pyqtSignal

from JMapCloud.core.services.qgis_project_manager import QGISProjectStyleManager
from JMapCloud.core.tasks.custom_qgs_task import CustomQgsTask


class ImportVectorStyleTask(CustomQgsTask):
    import_style_completed = pyqtSignal((object, object))

    def __init__(self, layer_properties) -> None:
        super().__init__("Import Style", QgsTask.CanCancel)
        self.layer_properties = layer_properties

    def run(self):
        if self.isCanceled():
            return False
        renderer = QGISProjectStyleManager.get_layer_styles(self.layer_properties["styleRules"])
        labeling = QGISProjectStyleManager.get_layer_labels(self.layer_properties["label"])

        self.import_style_completed.emit(renderer, labeling)
        return True


class ImportVectorTilesStyleTask(CustomQgsTask):
    import_style_completed = pyqtSignal((object, object))

    def __init__(self, layer_properties, element_type) -> None:
        super().__init__("Import Style", QgsTask.CanCancel)
        self.layer_properties = layer_properties
        self.element_type = element_type

    def run(
        self,
    ):
        if self.isCanceled():
            return False
        layer_properties = self.layer_properties
        element_type = self.element_type
        style_groups = QGISProjectStyleManager.get_mvt_layer_styles(layer_properties["styleRules"], element_type)
        labeling = QGISProjectStyleManager.get_mvt_layer_labels(layer_properties["label"], element_type)
        renderers = {}
        for styles in style_groups:
            renderer = QgsVectorTileBasicRenderer()
            renderer.setStyles(styles["style_list"])
            renderers[styles["name"]] = renderer

        self.import_style_completed.emit(renderers, labeling)
        return True
