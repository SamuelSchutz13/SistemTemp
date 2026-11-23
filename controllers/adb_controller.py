import os
import shutil

from PyQt5.QtCore import QProcess, QTimer
from PyQt5.QtWidgets import QMessageBox

from models.telemetry_model import COMANDO_ADB, TelemetryModel
from utils.generate_log import registrar_evento

TEXTO_CONECTAR = "📱  Conectar celular (USB)"
TEXTO_DESCONECTAR = "📱  Desconectar"
INTERVALO_MS = 5000


def achar_adb():
    """adb do PATH ou da pasta padrão do Android SDK; None se não estiver instalado."""
    if shutil.which("adb"):
        return shutil.which("adb")
    pastas = [os.environ.get("ANDROID_HOME"), os.environ.get("ANDROID_SDK_ROOT"),
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Android", "Sdk")]
    for pasta in filter(None, pastas):
        caminho = os.path.join(pasta, "platform-tools", "adb.exe" if os.name == "nt" else "adb")
        if os.path.isfile(caminho):
            return caminho
    return None


class AdbController:
    """Lê o celular pelo cabo USB (ou depuração por Wi-Fi) com o adb, sem app nenhum no celular.

    A cada 5 s roda COMANDO_ADB no celular, que lê direto os arquivos do kernel onde os drivers
    publicam os sensores (bateria, zonas térmicas). Só precisa da Depuração USB ligada no celular.
    """

    def __init__(self, botao, lbl_status, ao_receber, parent):
        self.botao = botao
        self.lbl_status = lbl_status
        self.ao_receber = ao_receber
        self.parent = parent
        self.adb = None
        self.ultimo_problema = None

        self.processo = QProcess(parent)
        self.processo.finished.connect(self._terminou)
        self.relogio = QTimer(parent)
        self.relogio.setInterval(INTERVALO_MS)
        self.relogio.timeout.connect(self._ler)
        self.botao.clicked.connect(self.alternar)

    def alternar(self):
        if self.relogio.isActive():
            self._desconectar("Usuário desconectou o celular.")
            return

        self.adb = achar_adb()
        if not self.adb:
            registrar_evento("ERROR", "adb não encontrado no PATH nem no Android SDK.")
            QMessageBox.warning(
                self.parent, "adb não encontrado",
                "Instale o Android SDK Platform-Tools e coloque a pasta platform-tools no PATH do Windows:\n"
                "https://developer.android.com/tools/releases/platform-tools",
            )
            return

        self.ultimo_problema = None
        self.botao.setText(TEXTO_DESCONECTAR)
        self._status("Procurando celular no USB…", "#F59E0B")
        registrar_evento("INFO", f"Lendo o celular pelo adb ({self.adb}).")
        self.relogio.start()
        self._ler()

    def _ler(self):
        if self.processo.state() != QProcess.NotRunning:
            # o adb travou desde a última leitura (5 s): encerra e tenta de novo na próxima
            self.processo.kill()
            self.processo.waitForFinished(1000)
            return
        self.processo.start(self.adb, ["shell", COMANDO_ADB])

    def _terminou(self, codigo, _estado):
        if not self.relogio.isActive():
            return  # desconectado enquanto o adb rodava
        saida = bytes(self.processo.readAllStandardOutput()).decode("utf-8", "ignore")
        erro = bytes(self.processo.readAllStandardError()).decode("utf-8", "ignore").strip()

        leitura = TelemetryModel.ler_leitura_adb(saida) if codigo == 0 else None
        if leitura is None:
            self._problema(erro or saida.strip()[:200] or "sem temperatura na resposta")
            return

        if self.ultimo_problema is not False:
            registrar_evento("INFO", f"Celular conectado: {leitura['nome']} ({leitura['fonte']}).")
        self.ultimo_problema = False
        self._status(f"Conectado: {leitura['nome']}", "#10B981")
        self.ao_receber(leitura)

    def _problema(self, erro):
        if "unauthorized" in erro:
            texto = "Aceite a depuração USB na tela do celular"
        elif "more than one" in erro:
            texto = "Mais de um aparelho no adb: deixe só um"
        elif "no devices" in erro or "not found" in erro:
            texto = "Celular não encontrado: ligue o cabo e a Depuração USB"
        else:
            texto = "Sem resposta do celular"
        if erro != self.ultimo_problema:  # registra só quando o problema muda, não a cada 5 s
            registrar_evento("WARNING", f"adb: {erro}")
            self.ultimo_problema = erro
        self._status(texto, "#F59E0B")

    def _status(self, texto, cor):
        self.lbl_status.setText(f"● {texto}")
        self.lbl_status.setStyleSheet(f"color: {cor};")

    def _desconectar(self, motivo):
        self.relogio.stop()
        if self.processo.state() != QProcess.NotRunning:
            self.processo.kill()
            self.processo.waitForFinished(1000)
        self.botao.setText(TEXTO_CONECTAR)
        self._status("Celular desconectado", "#64748B")
        registrar_evento("INFO", motivo)
