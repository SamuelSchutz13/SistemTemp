import sqlite3

from PyQt5.QtCore import QDate
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QDialog
from PyQt5.uic import loadUi

from models.telemetry_model import TelemetryModel
from controllers.config_controller import ConfigController
from controllers.grafico_controller import GraficoController
from controllers.historico_controller import HistoricoController, STATUS_VISUAL
from database.connection import DatabaseConnection
from utils.generate_log import registrar_evento


class MainController(QMainWindow):
    def __init__(self):
        super().__init__()

        try:
            loadUi("ui/main_window.ui", self)
            registrar_evento("INFO", "Inicializando a interface gráfica do Systemp...")
        except Exception as e:
            registrar_evento("ERROR", f"Falha crítica ao carregar o arquivo .ui: {e}")
            QMessageBox.critical(None, "Erro Crítico", f"Não foi possível carregar a interface gráfica:\n{e}")
            raise

        self.setWindowIcon(QIcon("assets/logo.svg"))

        self.model = TelemetryModel()
        self.ultima_leitura = None

        self.db = DatabaseConnection("database/systemp.db")
        conexao, cursor = self.conectar_banco()

        self.dateEdit.blockSignals(True)
        self.dateEdit.setDate(QDate.currentDate())
        self.dateEdit.blockSignals(False)

        self.grafico = GraficoController(self.graphWidget)
        self.historico = HistoricoController(self.tableHistorico, self.cbFiltro, self.dateEdit, conexao, cursor)

        self.btnConfig.clicked.connect(self.abrir_configuracoes)
        self.btnRegistrar.clicked.connect(self.simular_leitura)
        self.btnLimparTudo.clicked.connect(self.limpar_todo_historico)

        self.carregar_historico_banco()
        registrar_evento("INFO", "Janela principal e conexões configuradas com sucesso.")

    def conectar_banco(self):
        try:
            conexao, cursor = self.db.conectar()
            registrar_evento("INFO", "Conexão com o banco de dados SQLite estabelecida.")
            return conexao, cursor
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao conectar ao banco de dados: {e}")
            QMessageBox.critical(self, "Erro de Banco de Dados", f"Falha na conexão com o banco:\n{e}")
            return None, None

    def carregar_historico_banco(self):
        """Cria a tabela se preciso e carrega os dados salvos para a tabela e o gráfico."""
        try:
            self.historico.criar_tabela_banco()
        except (sqlite3.Error, AttributeError) as e:
            registrar_evento("ERROR", f"Erro ao criar tabela no banco: {e}")
            QMessageBox.warning(self, "Aviso", f"Não foi possível criar a tabela no banco de dados:\n{e}")
            return

        try:
            self.grafico.carregar(self.historico.carregar_banco())
        except (sqlite3.Error, ValueError, TypeError) as e:
            registrar_evento("ERROR", f"Erro ao carregar histórico do banco: {e}")
            QMessageBox.warning(self, "Aviso", f"Erro ao carregar dados históricos:\n{e}")

    def _atualizar_card_status(self, temperatura: float, umidade: float):
        texto, cor = STATUS_VISUAL[self.model.verificar_status_climatico(temperatura, umidade)]
        self.lblStatusAlerta.setText(texto)
        self.cardAlerta.setStyleSheet(f"#cardAlerta {{ background-color: {cor}; border: none; }}"
                                      "#cardAlerta QLabel { color: white; }")
        return texto

    def atualizar_telemetria(self, temperatura: float, umidade: float, pressao: float):
        try:
            self.ultima_leitura = (temperatura, umidade)
            orvalho = self.model.calcular_ponto_orvalho(temperatura, umidade)

            self.lblTemperatura.setText(f"{float(temperatura):.1f} °C")
            self.lblUmidade.setText(f"{float(umidade):.0f} %")
            self.lblPressao.setText(f"{float(pressao):.1f} hPa")

            status_txt = self._atualizar_card_status(temperatura, umidade)
            # o gráfico só ganha o ponto se a leitura foi salva, para não divergir da tabela
            if self.historico.adicionar(temperatura, umidade, pressao, orvalho, status_txt):
                self.grafico.adicionar_ponto(float(temperatura))
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao atualizar telemetria: {e}")

    def simular_leitura(self):
        try:
            registrar_evento("INFO", "Usuário acionou o botão 'Simular Leitura'.")

            temp_simulada, umid_simulada, press_simulada = self.model.gerar_leitura_simulada()

            if temp_simulada > self.model.temp_max_alerta:
                registrar_evento("WARNING", f"Alerta de Calor Extremo detectado: {temp_simulada}°C (Limite: {self.model.temp_max_alerta}°C).")
                QMessageBox.warning(
                    self,
                    "Alerta Climatológico",
                    f"Temperatura alta detectada: {temp_simulada}°C!\nAcima do limite de {self.model.temp_max_alerta}°C."
                )
            elif temp_simulada < self.model.temp_min_alerta:
                registrar_evento("WARNING", f"Alerta de Frio Intenso detectado: {temp_simulada}°C (Limite: {self.model.temp_min_alerta}°C).")
                QMessageBox.warning(
                    self,
                    "Alerta Climatológico",
                    f"Temperatura baixa detectada: {temp_simulada}°C!\nAbaixo do limite de {self.model.temp_min_alerta}°C."
                )

            self.atualizar_telemetria(temp_simulada, umid_simulada, press_simulada)
        except Exception as e:
            registrar_evento("ERROR", f"Erro na simulação de leitura: {e}")
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao simular a leitura:\n{e}")

    def abrir_configuracoes(self):
        try:
            registrar_evento("INFO", "Usuário abriu a tela de configurações de parâmetros.")

            dialog = ConfigController(
                self.model.temp_max_alerta,
                self.model.temp_min_alerta,
                self.model.umid_min_alerta,
                self
            )

            if dialog.exec_() == QDialog.Accepted:
                temp_max, temp_min, umid_min = dialog.get_parametros()

                # Validação lógica básica dos parâmetros configurados
                if temp_max <= temp_min:
                    QMessageBox.warning(self, "Aviso de Validação", "A temperatura máxima deve ser maior que a mínima!")
                    return

                self.model.temp_max_alerta = float(temp_max)
                self.model.temp_min_alerta = float(temp_min)
                self.model.umid_min_alerta = float(umid_min)

                registrar_evento(
                    "INFO",
                    f"Novos parâmetros salvos -> Máx: {temp_max}, Mín: {temp_min}, Umid. Mín: {umid_min}"
                )

                QMessageBox.information(self, "Sucesso", "Novos parâmetros de alertas climáticos salvos!")
                # reavalia a última leitura com os novos limites, sem inventar um registro novo
                if self.ultima_leitura:
                    self._atualizar_card_status(*self.ultima_leitura)
            else:
                registrar_evento("INFO", "Edição de parâmetros cancelada pelo usuário.")
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao abrir configurações: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao gerenciar configurações:\n{e}")

    def limpar_todo_historico(self):
        try:
            if self.historico.vazio():
                registrar_evento("INFO", "Tentativa de limpeza recusada: o histórico já estava vazio.")
                QMessageBox.information(self, "Informação", "O histórico já está vazio.")
                return

            registrar_evento("WARNING", "Usuário solicitou a limpeza de TODO o histórico de registros.")

            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Question)
            msg_box.setWindowTitle("Confirmar Limpeza")
            msg_box.setText("Tem certeza que deseja apagar TODO o histórico de registros?")

            btn_sim = msg_box.addButton(QMessageBox.Yes)
            btn_nao = msg_box.addButton(QMessageBox.No)

            btn_sim.setText("Sim")
            btn_nao.setText("Não")

            msg_box.setDefaultButton(btn_nao)
            msg_box.exec_()

            if msg_box.clickedButton() == btn_sim:
                self.historico.limpar()
                self.grafico.limpar()
                registrar_evento("ERROR", "Auditoria: Todo o histórico e o banco de dados foram apagados pelo operador.")
            else:
                registrar_evento("INFO", "Operação de limpeza de histórico cancelada pelo usuário.")
        except (sqlite3.Error, Exception) as e:
            registrar_evento("ERROR", f"Erro ao limpar histórico: {e}")
            QMessageBox.critical(self, "Erro", f"Não foi possível limpar o histórico:\n{e}")
