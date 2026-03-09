from qgis.core import QgsTask
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply


from ..tasks.custom_qgs_task import CustomQgsTask
from ..services.jmap_services_access import JMapMCS
from ..services.request_manager import RequestManager
from ..plugin_util import get_user_locale

MESSAGE_CATEGORY = "LOADJMCDATASOURCEREFERENCES"


class LoadJMCDataSourceReferencesTask(CustomQgsTask):
    tasks_completed = pyqtSignal(list) # Emits the list of project references that are referencing the datasource, each reference contains the project name and the list of layer names referencing the datasource

    def __init__(self, jmap_mcs: JMapMCS, data_source_id: str, project_id: str) -> None:
        super().__init__("Load JMC Data Source References", QgsTask.Flag.CanCancel)
        self._jmap_mcs = jmap_mcs
        self._data_source_id = data_source_id
        self._project_id = project_id

    def run(self):
        if self.isCanceled():
            return False
        
        reply: RequestManager.ResponseData = self._jmap_mcs.get_datasource_references_by_id(self._data_source_id)

        if reply.status != QNetworkReply.NetworkError.NoError:
            self.error_occur(
                self.tr("Error loading datasource references: {}").format(reply.error_message),
                MESSAGE_CATEGORY,
            )
            return False
        
        project_references: dict[str, list[str]] = reply.content["additionalInfo"]["references"]["projects"]

        if not project_references:
            self.tasks_completed.emit([])
            return True
        
        project_references.pop(self._project_id, None)  # Remove the current project from the references


        result: list[dict[str, list[str]]] = []  # List of dict with project name and list of layer names referencing the datasource
        locale: str = get_user_locale()

        for project_id, layers in project_references.items():
            project_data = self._jmap_mcs.get_project_by_id(project_id)
            layer_ids = layers["layers"] if "layers" in layers else []

            if not project_data:
                self.error_occur(
                    self.tr("Error loading project details for project id {}").format(project_id),
                    MESSAGE_CATEGORY,
                )
                continue
            
            if project_data.status != QNetworkReply.NetworkError.NoError:
                self.error_occur(
                    self.tr("Error loading project details for project id {}: {}").format(
                        project_id, project_data.error_message
                    ),
                    MESSAGE_CATEGORY,
                )
                continue
            
            project_name = project_data.content["name"][locale if locale in project_data.content["name"] else "en"]

            layer_names = []
            for layer_id in layer_ids:
                layer_data = self._jmap_mcs.get_layer_by_id(project_id, layer_id)

                if not layer_data:
                    self.error_occur(
                        self.tr("Error loading layer details for layer id {} in project id {}").format(
                            layer_id, project_id
                        ),
                        MESSAGE_CATEGORY,
                    )
                    continue
                
                if layer_data.status != QNetworkReply.NetworkError.NoError:
                    self.error_occur(
                        self.tr("Error loading layer details for layer id {} in project id {}: {}").format(
                            layer_id, project_id, layer_data.error_message
                        ),
                        MESSAGE_CATEGORY,
                    )
                    continue
                
                layer_name = layer_data.content["name"][locale if locale in layer_data.content["name"] else "en"]
                layer_names.append(layer_name)
            
            result.append({"project_name": project_name, "layer_names": layer_names})

        self.tasks_completed.emit(result)
        return True
