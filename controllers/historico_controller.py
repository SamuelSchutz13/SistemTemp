import datetime
import sqlite3

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QHeaderView, QTableWidgetItem

from models.telemetry_model import STATUS_ALERTA
from utils.generate_log import registrar_evento

# código do model -> (texto exibido, cor)
STATUS_VISUAL = {
    "ALERTA_QUENTE": ("ALERTA: BATERIA QUENTE", "#EF4444"),
    "ALERTA_FRIO": ("ALERTA: BATERIA FRIA", "#3B82F6"),
    "BATERIA_FRACA": ("BATERIA FRACA", "#F59E0B"),
    "CARREGANDO": ("CARREGANDO", "#06B6D4"),
    "NORMAL": ("APARELHO OK", "#10B981"),
    "INVALIDO": ("DADO INVÁLIDO", "#64748B"),
}
_COR_POR_TEXTO = dict(STATUS_VISUAL.values())
_TEXTOS_ALERTA = {STATUS_VISUAL[c][0] for c in STATUS_ALERTA}
COL_STATUS = 6


def _fmt(valor, casas):
    """Formata número para a tabela; campo que o aparelho não mandou aparece como '--'."""
    return "--" if valor is None else f"{float(valor):.{casas}f}"


class HistoricoController:
    """Cuida da tabela de leituras do aparelho, dos filtros (status e data) e da gravação no banco."""

    def __init__(self, table, cb_filtro, date_edit, conexao, cursor):
        self.table = table
        self.cb_filtro = cb_filtro
        self.date_edit = date_edit
        self.conexao = conexao
        self.cursor = cursor

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for col in (0, COL_STATUS):  # data/hora e status não podem cortar
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        self.table.verticalHeader().setVisible(False)

        self.cb_filtro.currentIndexChanged.connect(self.aplicar_filtros)
        self.date_edit.dateChanged.connect(self.aplicar_filtros)

    def criar_tabela_banco(self):
        """Cria a tabela de leituras se não existir. Lança sqlite3.Error."""
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS leituras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_hora TEXT,
                aparelho TEXT,
                temperatura REAL,
                nivel REAL,
                tensao REAL,
                ram REAL,
                status TEXT
            )
            """
        )
        self.conexao.commit()
        registrar_evento("INFO", "Verificação/Criação da tabela 'leituras' concluída no banco.")

    def carregar_banco(self):
        """Lê as leituras salvas, preenche a tabela e retorna [(temperatura, nivel)] para o gráfico."""
        self.cursor.execute(
            "SELECT data_hora, aparelho, temperatura, nivel, tensao, ram, status FROM leituras ORDER BY id ASC"
        )
        registros = self.cursor.fetchall()

        pontos = []
        for data_hora, aparelho, temp, nivel, tensao, ram, status in registros:
            if temp is None:
                continue
            self._inserir_linha(data_hora, aparelho, temp, nivel, tensao, ram, status)
            pontos.append((float(temp), nivel))

        self.aplicar_filtros()
        registrar_evento("INFO", f"Histórico carregado do banco: {len(registros)} leituras encontradas.")
        return pontos

    def adicionar(self, leitura, status):
        """Grava a leitura no banco e na tabela. Retorna False se não conseguiu gravar."""
        try:
            data_hora = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            valores = (leitura.get("nome"), leitura["temp"], leitura.get("nivel"), leitura.get("tensao"), leitura.get("ram"))

            self.cursor.execute(
                """
                INSERT INTO leituras (data_hora, aparelho, temperatura, nivel, tensao, ram, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (data_hora, *valores, str(status)),
            )
            self.conexao.commit()
            registrar_evento("INFO", f"Leitura gravada: {leitura.get('nome')} Temp={leitura['temp']}°C, "
                                     f"Bateria={leitura.get('nivel')}%, Status={status}")

            self._inserir_linha(data_hora, *valores, status)
            self.aplicar_filtros()
            self.table.scrollToBottom()
            return True
        except (sqlite3.Error, ValueError, TypeError, KeyError) as e:
            registrar_evento("ERROR", f"Erro ao adicionar leitura na tabela/banco: {e}")
            return False

    def _inserir_linha(self, data_hora, aparelho, temp, nivel, tensao, ram, status):
        dados = [str(data_hora), str(aparelho or "--"),
                 _fmt(temp, 1), _fmt(nivel, 0), _fmt(tensao, 2), _fmt(ram, 0), str(status)]
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col, valor in enumerate(dados):
            item = QTableWidgetItem(valor)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, col, item)
        self.table.item(row, COL_STATUS).setForeground(QColor(_COR_POR_TEXTO.get(dados[COL_STATUS], "#E2E8F0")))

    def aplicar_filtros(self):
        """Oculta ou exibe as linhas da tabela de acordo com a opção e data selecionadas."""
        try:
            opcao = self.cb_filtro.currentText()
            data_filtro = self.date_edit.date().toString("dd/MM/yyyy")

            for row in range(self.table.rowCount()):
                item_data = self.table.item(row, 0)
                item_status = self.table.item(row, COL_STATUS)
                if not item_data or not item_status:
                    continue

                status = item_status.text()
                if opcao == "Somente Alertas":
                    corresponde = status in _TEXTOS_ALERTA
                elif opcao == "Carregando":
                    corresponde = status == STATUS_VISUAL["CARREGANDO"][0]
                else:
                    corresponde = True

                exibir = corresponde and item_data.text().split(" ")[0] == data_filtro
                self.table.setRowHidden(row, not exibir)
        except Exception as e:
            registrar_evento("ERROR", f"Erro ao aplicar filtros na tabela: {e}")

    def vazio(self) -> bool:
        return self.table.rowCount() == 0

    def limpar(self):
        """Apaga as leituras do banco e da tabela. Lança sqlite3.Error."""
        self.cursor.execute("DELETE FROM leituras")
        self.conexao.commit()
        self.table.setRowCount(0)
