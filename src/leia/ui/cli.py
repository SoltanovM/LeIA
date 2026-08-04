"""Console script `leia` - sobe a UI Streamlit apontando pro `app.py` deste pacote.

Existe para dar um comando único (`leia`) mesmo o Streamlit precisando de um caminho de
arquivo. É o que o `[project.scripts]` do pyproject expõe.
A porta vem do `.env` via `Settings`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from leia.config import get_settings


def main() -> None:
    settings = get_settings()
    app = Path(__file__).with_name("app.py")
    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(app),
            "--server.port",
            str(settings.leia_port),
            "--server.address",
            "0.0.0.0",
            "--server.headless",
            "true",
        ],
        check=True,
    )
