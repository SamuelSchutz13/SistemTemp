import logging
import os

LOG_FILE = "logs/systemp.log"

def configurar_logger():
    """Configura e retorna o logger centralizado para o sistema Systemp."""
    logger = logging.getLogger("SystempLogger")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

logger = configurar_logger()

def registrar_evento(nivel: str, mensagem: str):
    """Registra eventos operacionais, erros ou desarmes com a severidade correta."""
    nivel = nivel.upper()
    if nivel == "INFO":
        logger.info(mensagem)
    elif nivel == "WARNING":
        logger.warning(mensagem)
    elif nivel == "ERROR":
        logger.error(mensagem)
    else:
        logger.info(mensagem)