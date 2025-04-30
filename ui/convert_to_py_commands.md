
# most be in .\plugin\jmap
cd C:path\to\plugin\jmap
# when  resources.qrc is updated
pyrcc5  .\resources.qrc -o .\resources_rc.py

after doing one of these function : update de last line "import resources_rc" to "from ..resources import resources_rc"
# when  login_dialog_base.ui is updated
pyuic5 .\ui\.ui\connection_dialog_base.ui -o .\ui\.py\connection_dialog_base.py
# when  load_project_dialog_base.ui is updated
pyuic5 .\ui\.ui\load_project_dialog_base.ui -o .\ui\.py\load_project_dialog_base.py
# when  export_project_dialog_base.ui is updated
pyuic5 .\ui\.ui\export_project_dialog_base.ui -o .\ui\.py\export_project_dialog_base.py
# when  action_dialog_base.ui is updated
pyuic5 .\ui\.ui\action_dialog_base.ui -o .\ui\.py\action_dialog_base.py
# when  warning_dialog_base.ui is updated
pyuic5 .\ui\.ui\warning_dialog_base.ui -o .\ui\.py\warning_dialog_base.py




