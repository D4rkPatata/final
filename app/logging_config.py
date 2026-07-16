"""Logging a consola para debug durante la demo + logger de auditoria clinica."""
import json
import logging
from datetime import datetime, timezone

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)


def get_logger(nombre: str) -> logging.Logger:
    return logging.getLogger(nombre)


def registrar_auditoria_clinica(dni: str, consulta: str) -> None:
    """Deja constancia de cada acceso a datos clinicos: timestamp, DNI, que se consulto."""
    settings.logs_dir.mkdir(parents=True, exist_ok=True)
    entrada = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dni": dni,
        "consulta": consulta,
    }
    with open(settings.auditoria_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
