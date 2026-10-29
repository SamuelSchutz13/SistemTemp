import datetime
import sqlite3

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHeaderView, QTableWidgetItem

from utils.generate_log import registrar_evento

# código do model -> (texto exibido, cor)
STATUS_VISUAL = {
    "ALERTA_CALOR": ("ALERTA: CALOR EXTREMO", "#EF4444"),
    "ALERTA_FRIO": ("ALERTA: FRIO INTENSO", "#3B82F6"),
    "ALERTA_SECO": ("ALERTA: AR MUITO SECO", "#F59E0B"),
    "NORMAL": ("CLIMA ESTÁVEL (OK)", "#10B981"),
    "INVALIDO": ("DADO INVÁLIDO", "#64748B"),
}
_COR_POR_TEXTO = dict(STATUS_VISUAL.values())


class HistoricoController:
    """Cuida da tabela de histórico, dos filtros (temperatura e data) e da gravação no banco."""

    def __init__(self, table, cb_filtro, date_edit, conexao, cursor):
        self.table = table
        self.cb_filtro = cb_filtro
        self.date_edit = date_edit
        self.conexao = conexao
        self.cursor = cursor

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)

        self.cb_filtro.currentIndexChanged.connect(self.aplicar_filtros)
        self.date_edit.dateChanged.connect(self.aplicar_filtros)

    def criar_tabela_banco(self):
        """Cria a tabela de histórico no banco de dados se não existir. Lança sqlite3.Error."""
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

    def carregar_banco(self):
        """Lê o histórico salvo, preenche a tabela e retorna a lista de temperaturas (para o gráfico)."""
        self.cursor.execute(
            "SELECT data_hora, temperatura, umidade, pressao, orvalho, status FROM historico ORDER BY id ASC"
        )
        registros = self.cursor.fetchall()

        temperaturas = []
        for row_data in registros:
            if len(row_data) < 6:
                continue

            data_hora, temp, umid, press, orvalho, status = row_data

            if temp is None or umid is None:
                continue

            self._inserir_linha([
                str(data_hora),
                f"{float(temp):.1f}",
                f"{float(umid):.0f}",
                f"{float(press):.1f}" if press is not None else "0.0",
                f"{float(orvalho):.1f}" if orvalho is not None else "0.0",
                str(status),
            ])
            temperaturas.append(float(temp))

        self.aplicar_filtros()
        registrar_evento("INFO", f"Histórico carregado do banco: {len(registros)} registros encontrados.")
        return temperaturas

    def adicionar(self, temp, umid, press, orvalho, status):
        """Grava a leitura no banco e na tabela. Retorna False se não conseguiu gravar."""
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

            self._inserir_linha([
                data_hora,
                f"{float(temp):.1f}",
                f"{float(umid):.0f}",
                f"{float(press):.1f}",
                f"{float(orvalho):.1f}",
                str(status),
            ])
            self.aplicar_filtros()
            self.table.scrollToBottom()
            return True
        except (sqlite3.Error, ValueError, TypeError) as e:
            registrar_evento("ERROR", f"Erro ao adicionar histórico na tabela/banco: {e}")
            return False

    def _inserir_linha(self, dados):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, valor in enumerate(dados):
            item = QTableWidgetItem(valor)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col, item)
        self.table.item(row, len(dados) - 1).setForeground(QColor(_COR_POR_TEXTO.get(dados[-1], "#E2E8F0")))

    def aplicar_filtros(self):
        """Oculta ou exibe as linhas da tabela de acordo com a opção e data selecionadas."""
        try:
            opcao_filtro = self.cb_filtro.currentText()
            data_filtro = self.date_edit.date().toString("dd/MM/yyyy")

            for row in range(self.table.rowCount()):
                item_data = self.table.item(row, 0)
                item_temp = self.table.item(row, 1)

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
                self.table.setRowHidden(row, not deve_exibir)
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao aplicar filtros na tabela: {e}")

    def vazio(self) -> bool:
        return self.table.rowCount() == 0

    def limpar(self):
        """Apaga o histórico do banco e da tabela. Lança sqlite3.Error."""
        self.cursor.execute("DELETE FROM historico")
        self.conexao.commit()
        self.table.setRowCount(0)
