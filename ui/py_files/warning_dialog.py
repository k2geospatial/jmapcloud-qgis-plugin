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

from qgis.PyQt import QtWidgets
from qgis.utils import iface

from .warning_dialog_base_ui import Ui_Dialog


class WarningDialog(QtWidgets.QDialog, Ui_Dialog):
    """Dialog to show warnings."""

    def __init__(self, html: str = ""):
        """Constructor."""
        super(WarningDialog, self).__init__(iface.mainWindow())

        self.setupUi(self)
        self.close_dialog_pushButton.clicked.connect(self.close)
        self.warning_textBrowser.setHtml(html)

    def set_html(self, html: str = ""):
        """
        Sets the HTML content of the warning text browser.

        :param html: The HTML string to be displayed.
        """

        self.warning_textBrowser.setHtml(html)
