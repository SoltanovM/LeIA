"""Converte um arquivo enviado (PDF / PNG / JPG) num bloco de conteúdo da Converse API.

Diferença importante em relação ao `documents.py` do `credit_ai_scratch` (que extraía
texto com pypdf): aqui NÃO extraímos texto nem rodamos OCR. A Converse API do Bedrock
aceita documentos e imagens NATIVAMENTE - o modelo (Nova / Claude) "enxerga" o arquivo:
    - PDF          -> bloco `document` (lê o texto E entende layout/tabelas)
    - PNG / JPG    -> bloco `image`    (visão multimodal, serve pra escaneado/print)

Assim o mesmo fluxo atende contrato escaneado, print de tela ou PDF nativo.
"""

from __future__ import annotations

import re
from pathlib import Path

# Extensões que o uploader aceita (Streamlit usa sem o ponto).
SUPPORTED_EXTENSIONS = ["pdf", "png", "jpg", "jpeg"]

# Extensão -> `format` que o Bedrock espera para imagens.
_IMAGE_FORMATS = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg"}
# Extensão -> `format` para documentos.
_DOC_FORMATS = {".pdf": "pdf"}


def _safe_doc_name(filename: str) -> str:
    """Sanitiza o nome do documento para o que o Bedrock aceita.

    A Converse API só permite nomes com [a-zA-Z0-9], espaço, hífen, () e []. Qualquer
    outro caractere vira '-', e espaços repetidos são colapsados.
    """
    stem = Path(filename).stem
    cleaned = re.sub(r"[^a-zA-Z0-9 \-\(\)\[\]]", "-", stem)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "documento"


def to_content_block(filename: str, data: bytes) -> dict:
    """Transforma os bytes de um arquivo no bloco de conteúdo da Converse API.

    Levanta `ValueError` se a extensão não for suportada.
    """
    ext = Path(filename).suffix.lower()

    if ext in _IMAGE_FORMATS:
        return {
            "image": {
                "format": _IMAGE_FORMATS[ext],
                "source": {"bytes": data},
            }
        }
    if ext in _DOC_FORMATS:
        return {
            "document": {
                "format": _DOC_FORMATS[ext],
                "name": _safe_doc_name(filename),
                "source": {"bytes": data},
            }
        }
    raise ValueError(f"Extensão não suportada: {ext!r} (use PDF, PNG ou JPG).")
