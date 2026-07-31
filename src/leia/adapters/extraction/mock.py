"""ADAPTER driven (offline) - extrator fake, determinístico. Roda sem AWS (backend=mock)."""

from __future__ import annotations

from collections.abc import Callable

from leia.domain.models import RawUpload

_IMAGE = {"png", "jpg", "jpeg"}


class MockExtractor:
    """Simula a extração: imagem = 1 página; PDF = 3 páginas de exemplo."""

    def extract(
        self, upload: RawUpload, on_page: Callable[[int, int], None] | None = None
    ) -> list[str]:
        if upload.extension in _IMAGE:
            texts = [
                (
                    f"[MOCK] Conteúdo transcrito da imagem '{upload.filename}' "
                    f"({len(upload.data)} bytes)."
                )
            ]
        else:
            texts = [
                f"[MOCK] Página {i} de '{upload.filename}' ({len(upload.data)} bytes).\n"
                "Defina BACKEND=aws no .env para extração real via Amazon Bedrock."
                for i in range(1, 4)
            ]
        total = len(texts)
        for i in range(1, total + 1):
            if on_page is not None:
                on_page(i, total)
        return texts
