import os
import sys

# os caminhos (ui/, logs/, database/, assets/) são relativos à pasta do projeto; tem que vir antes dos imports abaixo
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication
from controllers.main_controller import MainController
from utils.generate_log import registrar_evento


def aplicar_tema_escuro(app):
    """Paleta escura global: cobre pop-ups (QMessageBox), calendário e o que o .ui não estiliza."""
    app.setStyle("Fusion")
    p = QPalette()
    for papel, cor in [
        (QPalette.Window, "#0B1120"), (QPalette.WindowText, "#E2E8F0"),
        (QPalette.Base, "#111827"), (QPalette.AlternateBase, "#0F172A"),
        (QPalette.Text, "#E2E8F0"), (QPalette.Button, "#1F2937"),
        (QPalette.ButtonText, "#E2E8F0"), (QPalette.Highlight, "#EF4444"),
        (QPalette.HighlightedText, "#FFFFFF"), (QPalette.ToolTipBase, "#1F2937"),
        (QPalette.ToolTipText, "#E2E8F0"), (QPalette.PlaceholderText, "#64748B"),
    ]:
        p.setColor(papel, QColor(cor))
    app.setPalette(p)


def main():
    app = QApplication(sys.argv)
    aplicar_tema_escuro(app)

    registrar_evento("INFO", "Aplicação Systemp iniciada a partir do main.py.")

    window = MainController()
    window.show()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
