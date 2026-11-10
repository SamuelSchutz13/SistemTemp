import json
import random

# status que disparam o aviso (pop-up) quando o aparelho entra neles
STATUS_ALERTA = {"ALERTA_QUENTE", "ALERTA_FRIO", "BATERIA_FRACA"}


class TelemetryModel:
    """Regras das leituras do aparelho conectado: limites de alerta, status e validação do que chega do celular.

    Uma leitura é um dict: temp (°C), nivel (%), tensao (V), ram (% usada), carregando (bool),
    nome, modelo, android, saude (texto). Só temp é obrigatória.
    """

    def __init__(self):
        self.temp_max_alerta = 40.0  # °C, bateria quente
        self.temp_min_alerta = 10.0  # °C, bateria fria
        self.nivel_min_alerta = 20.0  # %, bateria fraca

    def verificar_status(self, leitura) -> str:
        """Retorna o código do status da leitura em relação aos limites configurados."""
        try:
            temp = float(leitura["temp"])
        except (KeyError, ValueError, TypeError):
            return "INVALIDO"

        nivel = leitura.get("nivel")
        if temp > self.temp_max_alerta:
            return "ALERTA_QUENTE"
        if temp < self.temp_min_alerta:
            return "ALERTA_FRIO"
        if leitura.get("carregando"):
            return "CARREGANDO"
        if nivel is not None and nivel < self.nivel_min_alerta:
            return "BATERIA_FRACA"
        return "NORMAL"

    @staticmethod
    def ler_leitura_celular(linha: str):
        """Converte uma linha JSON vinda do celular em leitura. Retorna None se for lixo ou sem temperatura válida."""
        try:
            dados = json.loads(linha)
        except ValueError:
            return None
        if not isinstance(dados, dict):
            return None

        # bateria de celular nunca sai disso; fora daqui é ruído
        temp = _numero(dados.get("temp"), -20, 80)
        if temp is None:
            return None
        return {
            "temp": round(temp, 1),
            "nivel": _numero(dados.get("nivel"), 0, 100),
            "tensao": _numero(dados.get("tensao"), 0, 10),
            "ram": _numero(dados.get("ram"), 0, 100),
            "carregando": dados.get("carregando") is True,
            "nome": _texto(dados.get("nome")) or "Celular",
            "modelo": _texto(dados.get("modelo")),
            "android": _texto(dados.get("android")),
            "saude": _texto(dados.get("saude")),
        }

    @staticmethod
    def gerar_leitura_simulada():
        """Leitura falsa para testar o app sem celular."""
        return {
            "temp": round(random.uniform(20.0, 48.0), 1),
            "nivel": float(random.randint(5, 100)),
            "tensao": round(random.uniform(3.5, 4.4), 2),
            "ram": float(random.randint(30, 90)),
            "carregando": random.random() < 0.3,
            "nome": "Simulado",
            "modelo": "Aparelho de teste",
            "android": "14",
            "saude": "Boa",
        }


def _numero(valor, minimo, maximo):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        return None
    valor = float(valor)
    return valor if minimo <= valor <= maximo else None  # NaN também cai fora


def _texto(valor):
    return valor.strip()[:40] if isinstance(valor, str) and valor.strip() else None
