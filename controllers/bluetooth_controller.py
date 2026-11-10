from PyQt5.QtCore import QProcess, QTimer
from PyQt5.QtSerialPort import QSerialPort, QSerialPortInfo
from PyQt5.QtWidgets import QInputDialog, QMessageBox

from models.telemetry_model import TelemetryModel
from utils.generate_log import registrar_evento

TEXTO_CONECTAR = "📱  Conectar celular"
TEXTO_DESCONECTAR = "📱  Desconectar"
# o celular manda a cada 5 s; 3 leituras perdidas = conexão caiu (a porta COM de Entrada não avisa)
SILENCIO_MS = 15000


class BluetoothController:
    """Recebe a temperatura da bateria do celular pela porta COM Bluetooth (SPP) que o Windows cria.

    O app Android (pasta android/) envia uma linha JSON por leitura, ex.: {"temp": 36.5, "nivel": 82, "nome": "Galaxy S21", ...}.
    """

    def __init__(self, botao, lbl_status, ao_receber, parent):
        self.botao = botao
        self.lbl_status = lbl_status
        self.ao_receber = ao_receber
        self.parent = parent

        self.porta = QSerialPort(parent)
        self.porta.readyRead.connect(self._ler)
        self.porta.errorOccurred.connect(self._erro)
        self.botao.clicked.connect(self.alternar)

        self.silencio = QTimer(parent)
        self.silencio.setSingleShot(True)
        self.silencio.setInterval(SILENCIO_MS)
        self.silencio.timeout.connect(self._sem_sinal)

    def alternar(self):
        if self.porta.isOpen():
            self._desconectar("Usuário desconectou o celular.")
            return

        portas = [f"{p.portName()} — {p.description()}" for p in QSerialPortInfo.availablePorts()]
        if not portas:
            resposta = QMessageBox.question(
                self.parent,
                "Nenhuma porta COM",
                "Nenhuma porta COM Bluetooth encontrada.\n\nNa janela que vai abrir: aba 'Portas COM' > Adicionar > "
                "Entrada (o dispositivo se conecta ao PC) > OK.\nDepois clique em 'Conectar celular' de novo.\n\n"
                "Abrir as opções de Bluetooth do Windows agora?",
            )
            if resposta == QMessageBox.Yes:
                QProcess.startDetached("rundll32.exe", ["shell32.dll,Control_RunDLL", "bthprops.cpl,,2"])
            return

        escolha, ok = QInputDialog.getItem(
            self.parent, "Conectar celular", "Porta COM Bluetooth (Entrada):", portas, 0, False
        )
        if not ok:
            return

        self.porta.setPortName(escolha.split(" — ")[0])
        if not self.porta.open(QSerialPort.ReadOnly):
            registrar_evento("ERROR", f"Falha ao abrir {self.porta.portName()}: {self.porta.errorString()}")
            QMessageBox.warning(self.parent, "Bluetooth", f"Não foi possível abrir a porta:\n{self.porta.errorString()}")
            return

        self.botao.setText(TEXTO_DESCONECTAR)
        self._status(f"Aguardando celular em {self.porta.portName()}…", "#F59E0B")
        registrar_evento("INFO", f"Aguardando leituras do celular em {self.porta.portName()}.")

    def _ler(self):
        while self.porta.canReadLine():
            linha = bytes(self.porta.readLine()).decode("utf-8", "ignore")
            leitura = TelemetryModel.ler_leitura_celular(linha)
            if leitura is None:
                registrar_evento("WARNING", f"Linha inválida recebida do celular: {linha[:200]!r}")
                continue
            nome = leitura["nome"]
            if not self.silencio.isActive():
                registrar_evento("INFO", f"Celular conectado: {nome} ({self.porta.portName()}).")
            self.silencio.start()
            self._status(f"Conectado: {nome}", "#10B981")
            self.ao_receber(leitura)
        # lixo sem quebra de linha não pode crescer para sempre no buffer
        if self.porta.bytesAvailable() > 4096:
            self.porta.clear()

    def _erro(self, erro):
        if erro == QSerialPort.NoError:
            return
        registrar_evento("ERROR", f"Erro na porta Bluetooth: {self.porta.errorString()}")
        if erro == QSerialPort.ResourceError:  # celular desligou/saiu do alcance
            self._desconectar("Conexão com o celular perdida.")
            QMessageBox.warning(self.parent, "Bluetooth", "A conexão com o celular caiu.")

    def _sem_sinal(self):
        registrar_evento("WARNING", f"Sem leituras do celular há {SILENCIO_MS // 1000} s.")
        self._status(f"Sem sinal, aguardando em {self.porta.portName()}…", "#F59E0B")

    def _status(self, texto, cor):
        self.lbl_status.setText(f"● {texto}")
        self.lbl_status.setStyleSheet(f"color: {cor};")

    def _desconectar(self, motivo):
        self.silencio.stop()
        self.porta.close()
        self.botao.setText(TEXTO_CONECTAR)
        self._status("Celular desconectado", "#64748B")
        registrar_evento("INFO", motivo)
