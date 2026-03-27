
from qgis.PyQt.QtCore import pyqtSignal
from qgis.PyQt.QtNetwork import QNetworkReply

from .custom_qgs_task import CustomQgsTask

from ..services.jmap_services_access import JMapMCS
from ..views import LayerData, ProjectData


MESSAGE_CATEGORY = "JMCRemoveLayerStyleTask"

class RemoveLayerStyleTask(CustomQgsTask):
   remove_layer_style_task_completed = pyqtSignal()

   def __init__(self, jmap_mcs: JMapMCS, layer_data: LayerData, project_data: ProjectData, new_style_rule_id: str = None):
      super().__init__(f"Remove styles from layer {layer_data.layer_name}", CustomQgsTask.CanCancel)
      self.jmap_mcs = jmap_mcs
      self.layer_data = layer_data
      self.project_data = project_data
      self.new_style_rule_id = new_style_rule_id
      self.set_total_steps(1)

   def run(self):
      if self.isCanceled():
         return False
      

      if not self.layer_data.jmc_layer_id:
         self.remove_layer_style_task_completed.emit()
         return True

      jmc_layer_id = self.layer_data.jmc_layer_id
      jmc_project_id = self.project_data.project_id
      organization_id = self.project_data.organization_id

      response = self.jmap_mcs.get_layer_style_rules(organization_id, jmc_project_id, jmc_layer_id)

      if response.status != QNetworkReply.NetworkError.NoError:
         error_message = self.tr("Error getting layer style rules: {}").format(response.error_message)
         self.error_occur(error_message, MESSAGE_CATEGORY)
         return False
      
      content = response.content

      if len(content) == 0:
         self.remove_layer_style_task_completed.emit()
         return True
      
      style_rules_ids = list(map(lambda style_rule: style_rule["id"], content))

      for style_rule_id in style_rules_ids:
         if self.isCanceled():
            return False
         
         if style_rule_id == self.new_style_rule_id:
            continue

         response = self.jmap_mcs.delete_layer_style_rule(organization_id, jmc_project_id, jmc_layer_id, style_rule_id)

         if response.status != QNetworkReply.NoError:
            error_message = self.tr("Error deleting layer style rule: {}").format(response.error_message)
            self.error_occur(error_message, MESSAGE_CATEGORY)

      self.remove_layer_style_task_completed.emit()
      return True
