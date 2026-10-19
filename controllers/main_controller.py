import datetime
import random
import sqlite3

from PyQt5.QtWidgets import (
    QMainWindow,
    QTableWidgetItem,
    QMessageBox,
    QHeaderView,
    QDialog
)
from PyQt5.QtCore import QDate

import pyqtgraph as pg
from PyQt5.uic import loadUi

from controllers.config_controller import ConfigController
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

        self.db = DatabaseConnection("database/systemp.db")
        self.conectar_banco()
        self.criar_tabela_banco()

        self.tableHistorico.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.temp_max_alerta = 35.0
        self.temp_min_alerta = 15.0
        self.umid_min_alerta = 30.0

        self.x_data = []
        self.y_data = []
        self.plot_line = None

        self._setup_graph()

        self.dateEdit.blockSignals(True)
        self.dateEdit.setDate(QDate.currentDate())
        self.dateEdit.blockSignals(False)

        self._conectar_sinais()
        
        self.carregar_historico_banco()
        registrar_evento("INFO", "Janela principal e conexões configuradas com sucesso.")

    def conectar_banco(self):
        try:
            self.conexao, self.cursor = self.db.conectar()
            registrar_evento("INFO", "Conexão com o banco de dados SQLite estabelecida.")
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao conectar ao banco de dados: {e}")
            QMessageBox.critical(self, "Erro de Banco de Dados", f"Falha na conexão com o banco:\n{e}")

    def criar_tabela_banco(self):
        """Cria a tabela de histórico no banco de dados se não existir."""
        try:
            self.cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS historico (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    data_hora TEXT,
                    temperatura REAL,
                    umidade REAL,
                    pressao REAL,
                    orvalho REAL,
                    status TEXT
                )
                """
            )
            self.conexao.commit()
            registrar_evento("INFO", "Verificação/Criação da tabela 'historico' concluída no banco.")
        except sqlite3.Error as e:
            registrar_evento("ERROR", f"Erro ao criar tabela no banco: {e}")
            QMessageBox.warning(self, "Aviso", f"Não foi possível criar a tabela no banco de dados:\n{e}")

    def carregar_historico_banco(self):
        """Carrega os dados salvos do banco para a tabela e o gráfico ao iniciar."""
        try:
            self.cursor.execute(
                "SELECT data_hora, temperatura, umidade, pressao, orvalho, status FROM historico ORDER BY id ASC"
            )
            registros = self.cursor.fetchall()

            for row_data in registros:
                if len(row_data) < 6:
                    continue
                
                data_hora, temp, umid, press, orvalho, status = row_data
                
                if temp is None or umid is None:
                    continue

                row = self.tableHistorico.rowCount()
                self.tableHistorico.insertRow(row)

                dados = [
                    str(data_hora),
                    f"{float(temp):.1f}",
                    f"{float(umid):.0f}",
                    f"{float(press):.1f}" if press is not None else "0.0",
                    f"{float(orvalho):.1f}" if orvalho is not None else "0.0",
                    str(status)
                ]

                for col, valor in enumerate(dados):
                    self.tableHistorico.setItem(
                        row,
                        col,
                        QTableWidgetItem(valor)
                    )

                novo_x = self.x_data[-1] + 1 if self.x_data else 1
                self.x_data.append(novo_x)
                self.y_data.append(float(temp))

            if self.plot_line and self.y_data:
                self.plot_line.setData(self.x_data, self.y_data)
            
            self.aplicar_filtros()
            registrar_evento("INFO", f"Histórico carregado do banco: {len(registros)} registros encontrados.")
        except (sqlite3.Error, ValueError, TypeError) as e:
            registrar_evento("ERROR", f"Erro ao carregar histórico do banco: {e}")
            QMessageBox.warning(self, "Aviso", f"Erro ao carregar dados históricos:\n{e}")

    def _setup_graph(self):
        try:
            self.graphWidget.setBackground("w")
            self.graphWidget.setTitle(
                "Histórico de Temperatura (°C)",
                color="#2C3E50",
                size="12pt"
            )
            self.graphWidget.showGrid(x=True, y=True)

            self.x_data = []
            self.y_data = []

            self.plot_line = self.graphWidget.plot(
                self.x_data,
                self.y_data,
                pen=pg.mkPen(color="#E74C3C", width=2),
                name="Temp (°C)"
            )
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao configurar o gráfico: {e}")

    def _conectar_sinais(self):
        self.btnConfig.clicked.connect(self.abrir_configuracoes)
        self.btnRegistrar.clicked.connect(self.simular_leitura)
        self.btnLimparTudo.clicked.connect(self.limpar_todo_historico)

        self.cbFiltro.currentIndexChanged.connect(self.aplicar_filtros)
        self.dateEdit.dateChanged.connect(self.aplicar_filtros)

    def calcular_ponto_orvalho(self, temp: float, umidade: float) -> float:
        """Calcula o ponto de orvalho aproximado com validação de parâmetros."""
        try:
            return round(float(temp) - ((100.0 - float(umidade)) / 5.0), 1)
        except (ValueError, TypeError):
            return 0.0

    def verificar_status_climatico(
        self,
        temperatura: float,
        umidade: float
    ) -> str:
        try:
            temp = float(temperatura)
            umid = float(umidade)

            if temp > self.temp_max_alerta:
                return "ALERTA: CALOR EXTREMO"
            elif temp < self.temp_min_alerta:
                return "ALERTA: FRIO INTENSO"
            elif umid < self.umid_min_alerta:
                return "ALERTA: AR MUITO SECO"
            return "CLIMA ESTÁVEL (OK)"
        except (ValueError, TypeError):
            return "DADO INVÁLIDO"

    def atualizar_telemetria(
        self,
        temperatura: float,
        umidade: float,
        pressao: float
    ):
        try:
            orvalho = self.calcular_ponto_orvalho(temperatura, umidade)
            status_txt = self.verificar_status_climatico(temperatura, umidade)

            self.lblTemperatura.setText(f"{float(temperatura):.1f} °C")
            self.lblUmidade.setText(f"{float(umidade):.0f} %")
            self.lblPressao.setText(f"{float(pressao):.1f} hPa")

            if temperatura > self.temp_max_alerta:
                style = "background-color: #E74C3C; border-radius: 8px; padding: 10px; color: white;"
            elif temperatura < self.temp_min_alerta:
                style = "background-color: #3498DB; border-radius: 8px; padding: 10px; color: white;"
            elif umidade < self.umid_min_alerta:
                style = "background-color: #E67E22; border-radius: 8px; padding: 10px; color: white;"
            else:
                style = "background-color: #2ECC71; border-radius: 8px; padding: 10px; color: white;"

            self.lblStatusAlerta.setText(status_txt)
            self.cardAlerta.setStyleSheet(style)

            self.adicionar_tabela_historico(
                temperatura,
                umidade,
                pressao,
                orvalho,
                status_txt
            )

            novo_x = self.x_data[-1] + 1 if self.x_data else 1
            self.x_data.append(novo_x)
            self.y_data.append(float(temperatura))

            if self.plot_line:
                self.plot_line.setData(self.x_data, self.y_data)
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao atualizar telemetria: {e}")

    def adicionar_tabela_historico(
        self,
        temp,
        umid,
        press,
        orvalho,
        status
    ):
        try:
            data_hora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")

            self.cursor.execute(
                """
                INSERT INTO historico (data_hora, temperatura, umidade, pressao, orvalho, status)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (data_hora, float(temp), float(umid), float(press), float(orvalho), str(status))
            )
            self.conexao.commit()
            registrar_evento("INFO", f"Registro gravado no banco de dados: Temp={temp}°C, Umid={umid}%, Status={status}")

            row = self.tableHistorico.rowCount()
            self.tableHistorico.insertRow(row)

            dados = [
                data_hora,
                f"{float(temp):.1f}",
                f"{float(umid):.0f}",
                f"{float(press):.1f}",
                f"{float(orvalho):.1f}",
                str(status)
            ]

            for col, valor in enumerate(dados):
                self.tableHistorico.setItem(
                    row,
                    col,
                    QTableWidgetItem(valor)
                )

            self.aplicar_filtros()
        except (sqlite3.Error, ValueError, TypeError) as e:
            registrar_evento("ERROR", f"Erro ao adicionar histórico na tabela/banco: {e}")

    def aplicar_filtros(self):
        try:
            opcao_filtro = self.cbFiltro.currentText()
            data_filtro = self.dateEdit.date().toString("dd/MM/yyyy")

            for row in range(self.tableHistorico.rowCount()):
                item_data = self.tableHistorico.item(row, 0)
                item_temp = self.tableHistorico.item(row, 1)

                if not item_data or not item_temp:
                    continue

                data_registro = item_data.text().split(" ")[0]

                try:
                    temp_valor = float(item_temp.text())
                except ValueError:
                    continue

                corresponde_data = (data_registro == data_filtro)
                corresponde_temp = True

                if opcao_filtro == "Temp. Alta (>30°C)":
                    corresponde_temp = temp_valor > 30.0
                elif opcao_filtro == "Temp. Baixa (<15°C)":
                    corresponde_temp = temp_valor < 15.0

                deve_exibir = corresponde_data and corresponde_temp
                self.tableHistorico.setRowHidden(row, not deve_exibir)
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao aplicar filtros na tabela: {e}")

    def simular_leitura(self):
        try:
            registrar_evento("INFO", "Usuário acionou o botão 'Simular Leitura'.")

            temp_simulada = round(random.uniform(10.0, 40.0), 1)
            umid_simulada = random.randint(20, 95)
            press_simulada = round(random.uniform(1000.0, 1025.0), 1)

            if temp_simulada > self.temp_max_alerta:
                registrar_evento("WARNING", f"Alerta de Calor Extremo detectado: {temp_simulada}°C (Limite: {self.temp_max_alerta}°C).")
                QMessageBox.warning(
                    self,
                    "Alerta Climatológico",
                    f"Temperatura alta detectada: {temp_simulada}°C!\nAcima do limite de {self.temp_max_alerta}°C."
                )
            elif temp_simulada < self.temp_min_alerta:
                registrar_evento("WARNING", f"Alerta de Frio Intenso detectado: {temp_simulada}°C (Limite: {self.temp_min_alerta}°C).")
                QMessageBox.warning(
                    self,
                    "Alerta Climatológico",
                    f"Temperatura baixa detectada: {temp_simulada}°C!\nAbaixo do limite de {self.temp_min_alerta}°C."
                )

            self.atualizar_telemetria(
                temp_simulada,
                umid_simulada,
                press_simulada
            )
        except Exception as e:
            registrar_evento("ERROR", f"Erro na simulação de leitura: {e}")
            QMessageBox.critical(self, "Erro", f"Ocorreu um erro ao simular a leitura:\n{e}")

    def abrir_configuracoes(self):
        try:
            registrar_evento("INFO", "Usuário abriu a tela de configurações de parâmetros.")
            
            dialog = ConfigController(
                self.temp_max_alerta,
                self.temp_min_alerta,
                self.umid_min_alerta,
                self
            )

            if dialog.exec_() == QDialog.Accepted:
                temp_max, temp_min, umid_min = dialog.get_parametros()

                # Validação lógica básica dos parâmetros configurados
                if temp_max <= temp_min:
                    QMessageBox.warning(self, "Aviso de Validação", "A temperatura máxima deve ser maior que a mínima!")
                    return

                self.temp_max_alerta = float(temp_max)
                self.temp_min_alerta = float(temp_min)
                self.umid_min_alerta = float(umid_min)

                registrar_evento(
                    "INFO", 
                    f"Novos parâmetros salvos -> Máx: {temp_max}, Mín: {temp_min}, Umid. Mín: {umid_min}"
                )

                QMessageBox.information(
                    self,
                    "Sucesso",
                    "Novos parâmetros de alertas climáticos salvos!"
                )
            else:
                registrar_evento("INFO", "Edição de parâmetros cancelada pelo usuário.")
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao abrir configurações: {e}")
            QMessageBox.critical(self, "Erro", f"Erro ao gerenciar configurações:\n{e}")

    def limpar_todo_historico(self):
        try:
            if self.tableHistorico.rowCount() == 0:
                registrar_evento("INFO", "Tentativa de limpeza recusada: o histórico já estava vazio.")
                QMessageBox.information(
                    self,
                    "Informação",
                    "O histórico já está vazio."
                )
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
                self.cursor.execute("DELETE FROM historico")
                self.conexao.commit()

                self.tableHistorico.setRowCount(0)

                self.x_data.clear()
                self.y_data.clear()

                if self.plot_line:
                    self.plot_line.setData([], [])
                    
                registrar_evento("ERROR", "Auditoria: Todo o histórico e o banco de dados foram apagados pelo operador.")
            else:
                registrar_evento("INFO", "Operação de limpeza de histórico cancelada pelo usuário.")
        except (sqlite3.Error, Exception) as e:
            registrar_evento("ERROR", f"Erro ao limpar histórico: {e}")
            QMessageBox.critical(self, "Erro", f"Não foi possível limpar o histórico:\n{e}")