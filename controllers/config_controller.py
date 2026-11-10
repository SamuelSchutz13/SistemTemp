from PyQt5.QtWidgets import QDialog, QMessageBox
from PyQt5.uic import loadUi


class ConfigController(QDialog):
    def __init__(self, temp_max_atual, temp_min_atual, nivel_min_atual, parent=None):
        super().__init__(parent)
        loadUi("ui/config_dialog.ui", self)

        self.spinTempMax.setValue(temp_max_atual)
        self.spinTempMin.setValue(temp_min_atual)
        
        self.spinNivelMin.setValue(int(nivel_min_atual))

        self.buttonBox.accepted.connect(self.validar_e_aceitar)
        self.buttonBox.rejected.connect(self.reject)

    def validar_e_aceitar(self):
        temp_max = self.spinTempMax.value()
        temp_min = self.spinTempMin.value()

        if temp_max <= temp_min:
            QMessageBox.warning(
                self,
                "Inconsistência nos Parâmetros",
                "A Temperatura Máxima de Alerta deve ser estritamente maior que a Temperatura Mínima!"
            )
            return

        self.accept()

    def get_parametros(self):
        return (
            self.spinTempMax.value(),
            self.spinTempMin.value(),
            self.spinNivelMin.value()
        )