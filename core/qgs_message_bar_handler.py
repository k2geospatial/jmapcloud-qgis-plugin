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


from qgis.core import Qgis
from qgis.utils import iface


class QgsMessageBarHandler:

    @staticmethod
    def send_message_to_message_bar(message: str, prefix: str = "", level: int = Qgis.MessageLevel.Info, duration: int = None):
        """
        Displays a message in the QGIS interface message bar.

        :param message: The message content to be displayed.
        :param prefix: An optional prefix to be added before the message.
        :param level: The message level indicating the type (e.g., Info, Warning, Critical).
        :param duration: The duration for which the message is displayed. If None, the default duration is used.
        """

        if duration is None:
            iface.messageBar().pushMessage(prefix, message, level=level)
        else:
            iface.messageBar().pushMessage(prefix, message, level=level, duration=duration)
