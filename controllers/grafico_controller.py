import pyqtgraph as pg


class GraficoController:
    """Cuida do gráfico de temperatura (pyqtgraph)."""

    def __init__(self, graph_widget):
        self.graph = graph_widget
        self.x_data = []
        self.y_data = []

        self.graph.setBackground("#111827")
        self.graph.setTitle("Histórico de Temperatura (°C)", color="#E2E8F0", size="11pt")
        self.graph.showGrid(x=True, y=True, alpha=0.15)
        self.graph.setLabel("left", "°C")
        self.graph.setLabel("bottom", "Leitura")
        for eixo in ("left", "bottom"):
            self.graph.getAxis(eixo).setTextPen("#64748B")
            self.graph.getAxis(eixo).setPen("#334155")

        self.plot_line = self.graph.plot(
            self.x_data,
            self.y_data,
            pen=pg.mkPen(color="#EF4444", width=2.5),
            symbol="o",
            symbolSize=6,
            symbolBrush="#EF4444",
            symbolPen=None,
            fillLevel=0,
            brush=pg.mkBrush(239, 68, 68, 40),
            name="Temp (°C)",
        )

    def adicionar_ponto(self, temperatura: float):
        novo_x = self.x_data[-1] + 1 if self.x_data else 1
        self.x_data.append(novo_x)
        self.y_data.append(temperatura)
        self.plot_line.setData(self.x_data, self.y_data)

    def carregar(self, temperaturas):
        self.y_data = list(temperaturas)
        self.x_data = list(range(1, len(self.y_data) + 1))
        self.plot_line.setData(self.x_data, self.y_data)

    def limpar(self):
        self.x_data.clear()
        self.y_data.clear()
        self.plot_line.setData([], [])
