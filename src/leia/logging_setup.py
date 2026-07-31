"""Configuração de logging - manda os logs `leia.*` pro stdout (aparecem no `docker logs`).

Sem um handler explícito, o Python usa o "handler de último recurso", que só emite WARNING+
- então os `logger.info(...)` (ingest, agente, chat) sumiam. Aqui garantimos INFO no stdout.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: int = logging.INFO) -> None:
    """Adiciona um StreamHandler (stdout) ao logger `leia`. Idempotente."""
    logger = logging.getLogger("leia")
    if logger.handlers:  # já configurado neste processo
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False  # evita duplicar via root
