"""Configuración centralizada de logging.

Sustituye a los `print()` que había dispersos por el código: ahora los mensajes
van a stdout con timestamp y nivel, y el pipeline deja de ser invisible cuando
corres en Docker o en el servidor.
"""

import logging
import sys

_CONFIGURED = False

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    """Configura el logging raíz una sola vez (idempotente)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
        force=True,
    )
    # httpx/httpcore logean cada request a INFO, ensucian la salida de los pipelines.
    for noisy in ("httpx", "httpcore", "trafilatura", "apscheduler.executors.default"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Devuelve un logger con el nombre dado (módulo o componente)."""
    if not _CONFIGURED:
        setup_logging()
    return logging.getLogger(name)