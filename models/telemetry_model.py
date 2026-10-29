import random

import numpy as np


class TelemetryModel:
    def __init__(self):
        self.temp_max_alerta = 35.0  # °C
        self.temp_min_alerta = 15.0  # °C
        self.umid_min_alerta = 30.0  # %

    def verificar_status_climatico(self, temperatura: float, umidade: float) -> str:
        """
        Verifica as leituras climáticas em relação aos limites configurados.
        Retorna o código do status.
        """
        try:
            temperatura, umidade = float(temperatura), float(umidade)
        except (ValueError, TypeError):
            return "INVALIDO"

        if temperatura > self.temp_max_alerta:
            return "ALERTA_CALOR"
        elif temperatura < self.temp_min_alerta:
            return "ALERTA_FRIO"
        elif umidade < self.umid_min_alerta:
            return "ALERTA_SECO"
        return "NORMAL"

    @staticmethod
    def calcular_ponto_orvalho(temp: float, umidade: float) -> float:
        """Calcula o Ponto de Orvalho aproximado (aproximação simplificada de Magnus-Tetens)."""
        try:
            return round(float(temp) - ((100.0 - float(umidade)) / 5.0), 1)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def gerar_leitura_simulada():
        """Retorna (temperatura, umidade, pressão) aleatórias para simular um sensor."""
        return (
            round(random.uniform(10.0, 40.0), 1),
            random.randint(20, 95),
            round(random.uniform(1000.0, 1025.0), 1),
        )

    def gerar_dados_pre_carregados(self):
        """
        Gera histórico inicial de 24h simulando o ciclo circadiano de temperatura.
        (Temperaturas mais baixas de madrugada, pico à tarde com ruído estocástico).
        """
        horas = np.linspace(0, 24, 50)
        temperaturas = 23 + 8 * np.sin((horas - 10) * np.pi / 12) + np.random.normal(0, 0.8, 50)

        return horas, np.round(temperaturas, 1)
