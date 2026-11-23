import random

# status que disparam o aviso (pop-up) quando o aparelho entra neles
STATUS_ALERTA = {"ALERTA_QUENTE", "ALERTA_FRIO", "BATERIA_FRACA"}

SAUDE = {"Good": "Boa", "Overheat": "Superaquecida", "Dead": "Morta", "Over voltage": "Sobretensão", "Cold": "Fria"}

# roda no celular num único `adb shell`: arquivos do kernel (2>/dev/null: o que o SELinux bloquear sai vazio),
# o dumpsys battery como reserva e os dados do aparelho; ler_leitura_adb() interpreta a saída
COMANDO_ADB = (
    "b=/sys/class/power_supply/battery; "
    "for f in temp capacity voltage_now current_now status health; do echo $f=$(cat $b/$f 2>/dev/null); done; "
    "for z in /sys/class/thermal/thermal_zone*; do echo zone=$(cat $z/type 2>/dev/null):$(cat $z/temp 2>/dev/null); done; "
    "awk '/^MemTotal/{print \"memtotal=\"$2} /^MemAvailable/{print \"memavail=\"$2}' /proc/meminfo; "
    "echo nome=$(settings get global device_name); "
    "echo modelo=$(getprop ro.product.manufacturer) $(getprop ro.product.model); "
    "echo android=$(getprop ro.build.version.release); "
    "dumpsys battery"
)


class TelemetryModel:
    """Regras das leituras do aparelho conectado: limites de alerta, status e interpretação do que vem do adb.

    Uma leitura é um dict: temp (°C), nivel (%), tensao (V), corrente (mA), cpu (°C), ram (% usada),
    carregando (bool), nome, modelo, android, saude, fonte (texto). Só temp é obrigatória.
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
        # carregando não vira status: pelo cabo USB o celular carrega sempre (aparece como ⚡ no card da bateria)
        if nivel is not None and nivel < self.nivel_min_alerta:
            return "BATERIA_FRACA"
        return "NORMAL"

    @staticmethod
    def ler_leitura_adb(saida: str):
        """Converte a saída de COMANDO_ADB em leitura. Retorna None se não veio temperatura válida.

        Prefere os arquivos do kernel (sysfs, o que o driver leu do chip da bateria); se o Android
        bloquear algum, usa o mesmo dado do `dumpsys battery`. "fonte" diz o que veio do kernel.
        """
        kernel, dumpsys, zonas = {}, {}, []
        for linha in saida.splitlines():
            if linha.startswith("zone="):
                tipo, _, valor = linha[5:].rpartition(":")
                zonas.append((tipo, _inteiro(valor)))
            elif "=" in linha:
                chave, _, valor = linha.partition("=")
                kernel[chave.strip()] = valor.strip()
            elif ":" in linha:
                chave, _, valor = linha.partition(":")
                dumpsys.setdefault(chave.strip(), valor.strip())  # dumpsys repete chaves em seções extras

        do_kernel = []

        def escolher(nome, chave_kernel, chave_dumpsys, converter_kernel, converter_dumpsys):
            valor = _inteiro(kernel.get(chave_kernel))
            if valor is not None:
                do_kernel.append(nome)
                return converter_kernel(valor)
            valor = _inteiro(dumpsys.get(chave_dumpsys))
            return None if valor is None else converter_dumpsys(valor)

        temp = _numero(escolher("temp", "temp", "temperature", lambda v: v / 10, lambda v: v / 10), -20, 80)
        if temp is None:
            return None
        escala = _inteiro(dumpsys.get("scale")) or 100
        nivel = escolher("nível", "capacity", "level", float, lambda v: v * 100 / escala)
        tensao = escolher("tensão", "voltage_now", "voltage", lambda v: v / 1_000_000, lambda v: v / 1000)  # µV / mV
        corrente = _inteiro(kernel.get("current_now"))
        if corrente is not None:
            do_kernel.append("corrente")
            # shortcut: o padrão é µA, mas alguns fabricantes gravam mA; acima de 20000 assume µA. O sinal varia por marca
            corrente = corrente / 1000 if abs(corrente) > 20_000 else float(corrente)

        # a maioria grava em m°C, alguns em °C
        cpus = [v / 1000 if v > 1000 else v for t, v in zonas if v is not None and "cpu" in t.lower()]
        cpu = max((c for c in cpus if 1 <= c <= 150), default=None)
        if cpu is not None:
            do_kernel.append("CPU")

        status = kernel.get("status") or {"2": "Charging", "5": "Full"}.get(dumpsys.get("status"), "")
        saude = kernel.get("health") or {"2": "Good", "3": "Overheat", "4": "Dead", "5": "Over voltage", "7": "Cold"}.get(
            dumpsys.get("health"), "")
        total, livre = _inteiro(kernel.get("memtotal")), _inteiro(kernel.get("memavail"))

        return {
            "temp": round(temp, 1),
            "nivel": _numero(nivel, 0, 100),
            "tensao": _numero(tensao, 0, 10),
            "corrente": corrente,
            "cpu": cpu and round(cpu, 1),
            "ram": _numero(100 - livre * 100 / total, 0, 100) if total and livre is not None else None,
            "carregando": status in ("Charging", "Full"),
            "nome": _texto(kernel.get("nome")) or "Celular",
            "modelo": _texto(kernel.get("modelo")),
            "android": _texto(kernel.get("android")),
            "saude": SAUDE.get(saude, saude or None),
            "fonte": "kernel (" + ", ".join(do_kernel) + ")" if do_kernel else "dumpsys",
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


def _inteiro(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _texto(valor):
    return valor.strip()[:40] if isinstance(valor, str) and valor.strip() else None
