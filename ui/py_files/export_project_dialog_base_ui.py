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


class Ui_Dialog(object):
    def setupUi(self, Dialog):
        Dialog.setObjectName("Dialog")
        Dialog.resize(703, 422)
        Dialog.setStyleSheet("background-color:rgb(36, 46, 52)")
        self.jmap_image_label = QtWidgets.QLabel(Dialog)
        self.jmap_image_label.setGeometry(QtCore.QRect(10, 10, 121, 71))
        self.jmap_image_label.setText("")
        self.jmap_image_label.setPixmap(QtGui.QPixmap(":/images/images/Logo_JMap_Cloud.svg"))
        self.jmap_image_label.setObjectName("jmap_image_label")
        self.widget = QtWidgets.QWidget(Dialog)
        self.widget.setGeometry(QtCore.QRect(10, 100, 681, 311))
        self.widget.setStyleSheet("background-color:rgb(220, 220, 220)\n" "")
        self.widget.setObjectName("widget")
        self.verticalLayoutWidget = QtWidgets.QWidget(self.widget)
        self.verticalLayoutWidget.setGeometry(QtCore.QRect(20, 10, 651, 281))
        self.verticalLayoutWidget.setObjectName("verticalLayoutWidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.verticalLayoutWidget)
        self.verticalLayout.setSizeConstraint(QtWidgets.QLayout.SetDefaultConstraint)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setObjectName("verticalLayout")
        self.title_label = QtWidgets.QLabel(self.verticalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.title_label.sizePolicy().hasHeightForWidth())
        self.title_label.setSizePolicy(sizePolicy)
        self.title_label.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.title_label.setStyleSheet("")
        self.title_label.setAlignment(QtCore.Qt.AlignCenter)
        self.title_label.setObjectName("title_label")
        self.verticalLayout.addWidget(self.title_label)
        self.project_title_label = QtWidgets.QLabel(self.verticalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.project_title_label.sizePolicy().hasHeightForWidth())
        self.project_title_label.setSizePolicy(sizePolicy)
        self.project_title_label.setStyleSheet("")
        self.project_title_label.setAlignment(QtCore.Qt.AlignLeading | QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self.project_title_label.setObjectName("project_title_label")
        self.verticalLayout.addWidget(self.project_title_label)
        self.project_title_lineEdit = QtWidgets.QLineEdit(self.verticalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.project_title_lineEdit.sizePolicy().hasHeightForWidth())
        self.project_title_lineEdit.setSizePolicy(sizePolicy)
        self.project_title_lineEdit.setStyleSheet("background-color:rgb(255, 255, 255);\n" "padding: 5px;")
        self.project_title_lineEdit.setText("")
        self.project_title_lineEdit.setPlaceholderText("")
        self.project_title_lineEdit.setObjectName("project_title_lineEdit")
        self.verticalLayout.addWidget(self.project_title_lineEdit)
        spacerItem = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.verticalLayout.addItem(spacerItem)
        self.error_label = QtWidgets.QLabel(self.verticalLayoutWidget)
        self.error_label.setStyleSheet("color:rgb(255, 0, 0)")
        self.error_label.setText("")
        self.error_label.setAlignment(QtCore.Qt.AlignCenter)
        self.error_label.setObjectName("error_label")
        self.verticalLayout.addWidget(self.error_label)
        self.export_project_pushButton = QtWidgets.QPushButton(self.verticalLayoutWidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.export_project_pushButton.sizePolicy().hasHeightForWidth())
        self.export_project_pushButton.setSizePolicy(sizePolicy)
        self.export_project_pushButton.setFocusPolicy(QtCore.Qt.WheelFocus)
        self.export_project_pushButton.setStyleSheet("background-color:rgb(255, 255, 255)")
        self.export_project_pushButton.setObjectName("export_project_pushButton")
        self.verticalLayout.addWidget(self.export_project_pushButton)

        self.retranslateUi(Dialog)
        QtCore.QMetaObject.connectSlotsByName(Dialog)

    def retranslateUi(self, Dialog):
        _translate = QtCore.QCoreApplication.translate
        Dialog.setWindowTitle(_translate("Dialog", "Export project"))
        self.title_label.setText(_translate("Dialog", "Export a project to JMap Cloud"))
        self.project_title_label.setText(_translate("Dialog", "Project title :"))
        self.export_project_pushButton.setText(_translate("Dialog", "Export"))


from JMapCloud import resources_rc
