import sys
from PyQt5.QtWidgets import QApplication
from controllers.main_controller import MainController
from utils.generate_log import registrar_evento

def main():
    app = QApplication(sys.argv)

    registrar_evento("INFO", "Aplicação Systemp iniciada a partir do main.py.")
    
    window = MainController()
    window.show()
    
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()