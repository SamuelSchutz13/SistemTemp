import json
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

LINHA = json.dumps({"temp": 36.54, "nivel": 82, "tensao": 4.12, "ram": 63, "carregando": True,
                    "nome": "Galaxy do Samuel", "modelo": "samsung SM-G991B", "android": "14", "saude": "Boa"})


def test_ler_leitura_celular():
    ler = TelemetryModel.ler_leitura_celular
    l = ler(LINHA + "\r\n")
    assert l["temp"] == 36.5 and l["nivel"] == 82 and l["tensao"] == 4.12 and l["carregando"] is True
    assert l["nome"] == "Galaxy do Samuel" and l["android"] == "14"

    so_temp = ler('{"temp": 30}')
    assert so_temp["nivel"] is None and so_temp["nome"] == "Celular" and so_temp["carregando"] is False

    assert ler('{"temp": 30, "nivel": 500, "nome": 7}')["nivel"] is None  # campo inválido vira vazio
    for lixo in ["abc", "", "36.5", "[1]", '{"nivel": 50}', '{"temp": 500}', '{"temp": NaN}', '{"temp": true}']:
        assert ler(lixo) is None, lixo


def test_status():
    m = TelemetryModel()
    assert m.verificar_status({"temp": 30, "nivel": 80}) == "NORMAL"
    assert m.verificar_status({"temp": 45, "nivel": 80, "carregando": True}) == "ALERTA_QUENTE"
    assert m.verificar_status({"temp": 5}) == "ALERTA_FRIO"
    assert m.verificar_status({"temp": 30, "nivel": 10}) == "BATERIA_FRACA"
    assert m.verificar_status({"temp": 30, "nivel": 10, "carregando": True}) == "CARREGANDO"
    assert m.verificar_status({"temp": "x"}) == "INVALIDO"


def test_historico_grava_recarrega_e_filtra():
    conexao = sqlite3.connect(":memory:")
    cb = QComboBox(); cb.addItems(["Todas as Leituras", "Somente Alertas", "Carregando"])
    data = QDateEdit(); data.setDate(QDate.currentDate())

    h = HistoricoController(QTableWidget(0, 7), cb, data, conexao, conexao.cursor())
    h.criar_tabela_banco()
    assert h.adicionar(TelemetryModel.ler_leitura_celular(LINHA), "CARREGANDO")
    assert h.adicionar({"temp": 45.0, "nome": "Simulado"}, "ALERTA: BATERIA QUENTE")

    h2 = HistoricoController(QTableWidget(0, 7), cb, data, conexao, conexao.cursor())
    assert h2.carregar_banco() == [(36.5, 82.0), (45.0, None)]
    assert [h2.table.item(0, c).text() for c in range(1, 7)] == ["Galaxy do Samuel", "36.5", "82", "4.12", "63", "CARREGANDO"]
    assert h2.table.item(1, 3).text() == "--"

    cb.setCurrentText("Somente Alertas")
    assert [h2.table.isRowHidden(r) for r in range(2)] == [True, False]
    cb.setCurrentText("Carregando")
    assert [h2.table.isRowHidden(r) for r in range(2)] == [False, True]
