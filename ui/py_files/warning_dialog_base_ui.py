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


from PyQt5 import QtCore, QtGui, QtWidgets
from ...resources_rc import qInitResources


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(611, 422)
        Dialog.setStyleSheet("background-color:rgb(36, 46, 52)")
        self.jmap_image_label = QtWidgets.QLabel(Dialog)
        self.jmap_image_label.setGeometry(QtCore.QRect(10, 10, 121, 71))
        self.jmap_image_label.setText("")
        self.jmap_image_label.setPixmap(QtGui.QPixmap(":/images/images/Logo_JMap_Cloud.svg"))
        self.jmap_image_label.setObjectName("jmap_image_label")
        self.widget = QtWidgets.QWidget(Dialog)
        self.widget.setGeometry(QtCore.QRect(10, 100, 591, 311))
        self.widget.setStyleSheet("background-color:rgb(240, 240, 240);\n" "border: 1px solid")
        self.widget.setObjectName("widget")
        self.warning_textBrowser = QtWidgets.QTextBrowser(self.widget)
        self.warning_textBrowser.setGeometry(QtCore.QRect(15, 21, 561, 221))
        self.warning_textBrowser.setStyleSheet("border:none;\n" "")
        self.warning_textBrowser.setObjectName("warning_textBrowser")
        self.close_dialog_pushButton = QtWidgets.QPushButton(self.widget)
        self.close_dialog_pushButton.setGeometry(QtCore.QRect(460, 260, 111, 41))
        self.close_dialog_pushButton.setStyleSheet("background-color: white;\n" "")
        self.close_dialog_pushButton.setObjectName("close_dialog_pushButton")

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Warning"))
        self.warning_textBrowser.setHtml(
            _translate(
                "Dialog",
                '<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">\n'
                '<html><head><meta name="qrichtext" content="1" /><style type="text/css">\n'
                "p, li { white-space: pre-wrap; }\n"
                "</style></head><body style=\" font-family:'MS Shell Dlg 2'; font-size:7.8pt; font-weight:400; font-style:normal;\">\n"
                '<p align="center" style="-qt-paragraph-type:empty; margin-top:18px; margin-bottom:12px; margin-left:0px; margin-right:0px; -qt-block-indent:0; text-indent:0px;"><br /></p></body></html>',
            )
        )
        self.close_dialog_pushButton.setText(_translate("Dialog", "Close"))


qInitResources()
