import os
import sqlite3
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt5.QtCore import QDate
from PyQt5.QtWidgets import QApplication, QComboBox, QDateEdit, QTableWidget

from controllers.historico_controller import HistoricoController
from models.telemetry_model import TelemetryModel

app = QApplication.instance() or QApplication([])

DUMPSYS = """Current Battery Service state:
  AC powered: false
  USB powered: true
  status: 2
  health: 2
  level: 41
  scale: 100
  voltage: 3870
  temperature: 298
"""
KERNEL = """temp=365
capacity=82
voltage_now=4120000
current_now=-512000
status=Charging
health=Good
zone=cpu-0-0-usr:45300
zone=cpu-1-2-usr:51800
zone=battery:36500
memtotal=8000000
memavail=2960000
nome=Galaxy do Samuel
modelo=samsung SM-G991B
android=14
"""
# o SELinux bloqueou tudo: cat sai vazio e só o dumpsys responde
BLOQUEADO = "temp=\ncapacity=\nvoltage_now=\ncurrent_now=\nstatus=\nhealth=\nzone=:\nnome=Moto\n" + DUMPSYS
SAIDA_ADB = KERNEL + DUMPSYS


def test_ler_leitura_adb_do_kernel():
    l = TelemetryModel.ler_leitura_adb(SAIDA_ADB.replace("\n", "\r\n"))  # adb antigo no Windows devolve \r\n
    assert l["temp"] == 36.5 and l["nivel"] == 82 and l["tensao"] == 4.12 and l["carregando"] is True
    assert l["corrente"] == -512 and l["cpu"] == 51.8 and l["ram"] == 63 and l["saude"] == "Boa"
    assert l["nome"] == "Galaxy do Samuel" and l["modelo"] == "samsung SM-G991B" and l["android"] == "14"
    assert l["fonte"] == "kernel (temp, nível, tensão, corrente, CPU)"


def test_ler_leitura_adb_bloqueado_usa_dumpsys():
    l = TelemetryModel.ler_leitura_adb(BLOQUEADO)
    assert l["temp"] == 29.8 and l["nivel"] == 41 and l["tensao"] == 3.87 and l["carregando"] is True
    assert l["corrente"] is None and l["cpu"] is None and l["ram"] is None and l["saude"] == "Boa"
    assert l["nome"] == "Moto" and l["fonte"] == "dumpsys"


def test_ler_leitura_adb_sem_temperatura():
    for lixo in ["", "error: no devices/emulators found", "temp=abc", "temp=5000"]:
        assert TelemetryModel.ler_leitura_adb(lixo) is None, lixo


def test_status():
    m = TelemetryModel()
    assert m.verificar_status({"temp": 30, "nivel": 80}) == "NORMAL"
    assert m.verificar_status({"temp": 45, "nivel": 80, "carregando": True}) == "ALERTA_QUENTE"
    assert m.verificar_status({"temp": 5}) == "ALERTA_FRIO"
    assert m.verificar_status({"temp": 30, "nivel": 10}) == "BATERIA_FRACA"
    assert m.verificar_status({"temp": 30, "nivel": 80, "carregando": True}) == "NORMAL"
    assert m.verificar_status({"temp": 30, "nivel": 10, "carregando": True}) == "BATERIA_FRACA"  # USB carrega devagar
    assert m.verificar_status({"temp": "x"}) == "INVALIDO"


def test_historico_grava_recarrega_e_filtra():
    conexao = sqlite3.connect(":memory:")
    cb = QComboBox(); cb.addItems(["Todas as Leituras", "Somente Alertas"])
    data = QDateEdit(); data.setDate(QDate.currentDate())

    h = HistoricoController(QTableWidget(0, 7), cb, data, conexao, conexao.cursor())
    h.criar_tabela_banco()
    assert h.adicionar(TelemetryModel.ler_leitura_adb(SAIDA_ADB), "APARELHO OK")
    assert h.adicionar({"temp": 45.0, "nome": "Simulado"}, "ALERTA: BATERIA QUENTE")

    h2 = HistoricoController(QTableWidget(0, 7), cb, data, conexao, conexao.cursor())
    assert h2.carregar_banco() == [(36.5, 82.0), (45.0, None)]
    assert [h2.table.item(0, c).text() for c in range(1, 7)] == ["Galaxy do Samuel", "36.5", "82", "4.12", "63", "APARELHO OK"]
    assert h2.table.item(1, 3).text() == "--"

    cb.setCurrentText("Somente Alertas")
    assert [h2.table.isRowHidden(r) for r in range(2)] == [True, False]
    cb.setCurrentText("Todas as Leituras")
    assert [h2.table.isRowHidden(r) for r in range(2)] == [False, False]


def test_historico_segue_virada_do_dia_e_limita_linhas(monkeypatch):
    import controllers.historico_controller as hc
    monkeypatch.setattr(hc, "MAX_LINHAS", 2)
    conexao = sqlite3.connect(":memory:")
    cb = QComboBox(); cb.addItems(["Todas as Leituras"])
    ontem = QDate.currentDate().addDays(-1)
    data = QDateEdit(); data.setDate(ontem)

    h = HistoricoController(QTableWidget(0, 7), cb, data, conexao, conexao.cursor())
    h.criar_tabela_banco()
    h.hoje = ontem  # o app foi aberto ontem e passou da meia-noite
    for _ in range(3):
        assert h.adicionar({"temp": 30.0}, "APARELHO OK")
    assert data.date() == QDate.currentDate() and not h.table.isRowHidden(1)
    assert h.table.rowCount() == 2  # a mais antiga saiu da tela

    h2 = HistoricoController(QTableWidget(0, 7), cb, data, conexao, conexao.cursor())
    assert len(h2.carregar_banco()) == 2  # o banco tem 3, a tela carrega só as 2 últimas
