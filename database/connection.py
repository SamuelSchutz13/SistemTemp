import sqlite3

class DatabaseConnection:
    def __init__(self, db_name="systemp.db"):
        self.db_name = db_name
        self.conexao = None
        self.cursor = None

    def conectar(self):
        """Estabelece a conexão com o banco de dados SQLite."""
        if self.conexao is None:
            self.conexao = sqlite3.connect(self.db_name)
            self.cursor = self.conexao.cursor()
        return self.conexao, self.cursor

    def fechar(self):
        """Fecha a conexão com o banco de dados se estiver aberta."""
        if self.conexao:
            self.conexao.close()
            self.conexao = None
            self.cursor = None