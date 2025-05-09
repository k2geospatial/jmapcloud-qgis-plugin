FORMS = ../ui/ui_files/action_dialog_base.ui \
        ../ui/ui_files/connection_dialog_base.ui \
        ../ui/ui_files/export_project_dialog_base.ui \
        ../ui/ui_files/open_project_dialog_base.ui \
        ../ui/ui_files/warning_dialog_base.ui 

SOURCES = ../jmap_cloud.py \
          ../ui/py_files/action_dialog.py \
          ../ui/py_files/action_dialog_base_ui.py \
          ../ui/py_files/connection_dialog.py \
          ../ui/py_files/connection_dialog_base_ui.py \
          ../ui/py_files/export_project_dialog.py \
          ../ui/py_files/export_project_dialog_base_ui.py \
          ../ui/py_files/open_project_dialog.py \
          ../ui/py_files/open_project_dialog_base_ui.py \
          ../ui/py_files/warning_dialog.py \
          ../ui/py_files/warning_dialog_base_ui.py \
          ../core/DTOS/compound_style_dto.py \
          ../core/DTOS/condition_dto.py \
          ../core/DTOS/criteria_dto.py \
          ../core/DTOS/datasource_dto.py \
          ../core/DTOS/dto.py \
          ../core/DTOS/labeling_config_dto.py \
          ../core/DTOS/layer_dto.py \
          ../core/DTOS/line_style_dto.py \
          ../core/DTOS/mouse_over_config_dto.py \
          ../core/DTOS/point_style_dto.py \
          ../core/DTOS/polygon_style_dto.py \
          ../core/DTOS/project_dto.py \
          ../core/DTOS/style_dto.py \
          ../core/DTOS/style_map_scale_dto.py \
          ../core/DTOS/style_rule_dto.py \
          ../core/services/auth_manager.py \
          ../core/services/export_project_manager.py \
          ../core/services/files_manager.py \
          ../core/services/import_project_manager.py \
          ../core/services/jmap_services_access.py \
          ../core/services/request_manager.py \
          ../core/services/session_manager.py \
          ../core/services/style_manager.py \
          ../core/tasks/create_jmc_project_task.py \
          ../core/tasks/custom_qgs_task.py \
          ../core/tasks/export_layer_style_task.py \
          ../core/tasks/load_style_task.py \
          ../core/tasks/write_layer_tasks.py 
          ../core/qgs_message_bar_handler.py \
          ../core/recurring_event.py \
          ../core/signal_object.py \
          ../core/views.py \
          
TRANSLATIONS = jmap_cloud_fr.ts


