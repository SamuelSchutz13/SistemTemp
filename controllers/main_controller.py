import sqlite3

from PyQt5.QtCore import QDate
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QMessageBox, QDialog
from PyQt5.uic import loadUi

from models.telemetry_model import STATUS_ALERTA, TelemetryModel
from controllers.bluetooth_controller import BluetoothController
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
        self.ultimo_status = None

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
        self.bluetooth = BluetoothController(self.btnBluetooth, self.lblBluetoothStatus, self.atualizar_leitura, self)

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

    def _atualizar_card_status(self, leitura):
        codigo = self.model.verificar_status(leitura)
        texto, cor = STATUS_VISUAL[codigo]
        self.lblStatusAlerta.setText(texto)
        self.cardAlerta.setStyleSheet(f"#cardAlerta {{ background-color: {cor}; border: none; }}"
                                      "#cardAlerta QLabel { color: white; }")
        return codigo, texto

    def atualizar_leitura(self, leitura):
        """Mostra uma leitura do aparelho (celular ou simulada) nos cards, no histórico e no gráfico."""
        try:
            self.ultima_leitura = leitura
            nivel, tensao, ram = leitura.get("nivel"), leitura.get("tensao"), leitura.get("ram")

            self.lblTemperatura.setText(f"{leitura['temp']:.1f} °C")
            self.lblBateria.setText("-- %" if nivel is None else f"{nivel:.0f} %" + (" ⚡" if leitura.get("carregando") else ""))
            self.lblTensao.setText("-- V" if tensao is None else f"{tensao:.2f} V")
            self.lblRam.setText("-- %" if ram is None else f"{ram:.0f} %")
            detalhes = [leitura.get("nome"), leitura.get("modelo"),
                        leitura.get("android") and f"Android {leitura['android']}",
                        leitura.get("saude") and f"Saúde: {leitura['saude']}"]
            self.lblSubtitulo.setText("  ·  ".join(d for d in detalhes if d))

            codigo, status_txt = self._atualizar_card_status(leitura)
            # o gráfico só ganha o ponto se a leitura foi salva, para não divergir da tabela
            if self.historico.adicionar(leitura, status_txt):
                self.grafico.adicionar_ponto(leitura["temp"], nivel)
            self._avisar_se_entrou_em_alerta(codigo, status_txt, leitura)
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao atualizar leitura do aparelho: {e}")

    def _avisar_se_entrou_em_alerta(self, codigo, texto, leitura):
        # só avisa na transição: com o celular mandando a cada 5 s, avisar sempre viraria spam
        anterior, self.ultimo_status = self.ultimo_status, codigo
        if codigo not in STATUS_ALERTA or codigo == anterior:
            return
        nivel = leitura.get("nivel")
        nivel_txt = "--" if nivel is None else f"{nivel:.0f}"
        registrar_evento("WARNING", f"{texto}: {leitura.get('nome')} Temp={leitura['temp']}°C, Bateria={nivel_txt}%.")
        QMessageBox.warning(
            self, "Alerta do Aparelho",
            f"{texto}\n\n{leitura.get('nome')}: {leitura['temp']:.1f} °C, bateria em {nivel_txt} %.\n"
            f"Limites: {self.model.temp_min_alerta:.0f}–{self.model.temp_max_alerta:.0f} °C, "
            f"mínimo {self.model.nivel_min_alerta:.0f} % de bateria.",
        )

    def simular_leitura(self):
        try:
            registrar_evento("INFO", "Usuário acionou o botão 'Simular Leitura'.")
            self.atualizar_leitura(self.model.gerar_leitura_simulada())
        except Exception as e:
            registrar_evento("ERROR", f"Erro na simulação de leitura: {e}")
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao simular a leitura:\n{e}")

    def abrir_configuracoes(self):
        try:
            registrar_evento("INFO", "Usuário abriu a tela de configurações de parâmetros.")

            dialog = ConfigController(
                self.model.temp_max_alerta,
                self.model.temp_min_alerta,
                self.model.nivel_min_alerta,
                self
            )

            if dialog.exec_() == QDialog.Accepted:
                temp_max, temp_min, nivel_min = dialog.get_parametros()  # já validados pelo diálogo
                self.model.temp_max_alerta = float(temp_max)
                self.model.temp_min_alerta = float(temp_min)
                self.model.nivel_min_alerta = float(nivel_min)

                registrar_evento(
                    "INFO",
                    f"Novos parâmetros salvos -> Temp. máx: {temp_max}, Temp. mín: {temp_min}, Bateria mín: {nivel_min}"
                )

                QMessageBox.information(self, "Sucesso", "Novos limites de alerta do aparelho salvos!")
                # reavalia a última leitura com os novos limites, sem inventar um registro novo
                if self.ultima_leitura:
                    self.ultimo_status = self._atualizar_card_status(self.ultima_leitura)[0]
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

            if self._confirmar("Confirmar Limpeza", "Tem certeza que deseja apagar TODO o histórico de registros?"):
                self.historico.limpar()
                self.grafico.limpar()
                registrar_evento("WARNING", "Auditoria: Todo o histórico e o banco de dados foram apagados pelo operador.")
            else:
                registrar_evento("INFO", "Operação de limpeza de histórico cancelada pelo usuário.")
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao limpar histórico: {e}")
            QMessageBox.critical(self, "Erro", f"Não foi possível limpar o histórico:\n{e}")

    def _confirmar(self, titulo, texto):
        """Pergunta Sim/Não em português, com 'Não' como padrão para evitar apagar sem querer."""
        caixa = QMessageBox(QMessageBox.Question, titulo, texto, parent=self)
        sim = caixa.addButton("Sim", QMessageBox.YesRole)
        caixa.setDefaultButton(caixa.addButton("Não", QMessageBox.NoRole))
        caixa.exec_()
        return caixa.clickedButton() is sim
