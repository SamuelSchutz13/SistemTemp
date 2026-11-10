import math

import pyqtgraph as pg


class GraficoController:
    """Gráfico do aparelho: temperatura da bateria (°C) e nível da bateria (%), que cabem no mesmo eixo 0–100."""

    def __init__(self, graph_widget):
        self.graph = graph_widget
        self.x_data = []
        self.temps = []
        self.niveis = []

        self.graph.setBackground("#111827")
        self.graph.setTitle("Bateria do aparelho", color="#E2E8F0", size="11pt")
        self.graph.showGrid(x=True, y=True, alpha=0.15)
        self.graph.setLabel("left", "°C / %")
        self.graph.setLabel("bottom", "Leitura")
        for eixo in ("left", "bottom"):
            self.graph.getAxis(eixo).setTextPen("#64748B")
            self.graph.getAxis(eixo).setPen("#334155")
        self.graph.addLegend(offset=(10, 10), labelTextColor="#94A3B8")

        self.linha_temp = self.graph.plot(
            [], [],
            pen=pg.mkPen(color="#EF4444", width=2.5),
            symbol="o", symbolSize=6, symbolBrush="#EF4444", symbolPen=None,
            fillLevel=0, brush=pg.mkBrush(239, 68, 68, 40),
            name="Temperatura (°C)",
        )
        self.linha_nivel = self.graph.plot(
            [], [],
            pen=pg.mkPen(color="#10B981", width=2),
            symbol="o", symbolSize=5, symbolBrush="#10B981", symbolPen=None,
            connect="finite",  # leitura sem nível vira buraco na linha
            name="Bateria (%)",
        )

    def _redesenhar(self):
        self.linha_temp.setData(self.x_data, self.temps)
        self.linha_nivel.setData(self.x_data, self.niveis)

    def adicionar_ponto(self, temperatura, nivel):
        self.x_data.append(self.x_data[-1] + 1 if self.x_data else 1)
        self.temps.append(float(temperatura))
        self.niveis.append(math.nan if nivel is None else float(nivel))
        self._redesenhar()

    def carregar(self, pontos):
        self.temps = [float(t) for t, _ in pontos]
        self.niveis = [math.nan if n is None else float(n) for _, n in pontos]
        self.x_data = list(range(1, len(pontos) + 1))
        self._redesenhar()

    def limpar(self):
        self.x_data, self.temps, self.niveis = [], [], []
        self._redesenhar()
