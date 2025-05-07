
# most be in .\plugin\jmap
cd C:path\to\plugin\jmap
# when  resources.qrc is updated
pyrcc5  ..\resources.qrc -o ..\resources_rc.py

after doing one of these function : update de last line "import resources_rc" to "from ..resources import resources_rc"
# when  login_dialog_base.ui is updated
pyuic5 ..\ui\ui_files\connection_dialog_base.ui -o ..\ui\py_files\connection_dialog_base.py
# when  load_project_dialog_base.ui is updated
pyuic5 ..\ui\ui_files\load_project_dialog_base.ui -o ..\ui\py_files\load_project_dialog_base.py
# when  export_project_dialog_base.ui is updated
pyuic5 ..\ui\ui_files\export_project_dialog_base.ui -o ..\ui\py_files\export_project_dialog_base.py
# when  action_dialog_base.ui is updated
pyuic5 ..\ui\ui_files\action_dialog_base.ui -o ..\ui\py_files\action_dialog_base.py
# when  warning_dialog_base.ui is updated
pyuic5 ..\ui\ui_files\warning_dialog_base.ui -o ..\ui\py_files\warning_dialog_base.py




