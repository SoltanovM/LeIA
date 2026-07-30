"""Testa o CASO DE USO (`LeiaService.ingest`) com adapters MOCK — SEM AWS/Postgres.

Prova o benefício central do hexagonal: o núcleo é testável isoladamente. Usamos os adapters
mock reais (extractor/repo/vetor) + um blob em memória — nada de boto3, psycopg ou rede.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from leia.adapters.extraction.mock import MockExtractor
from leia.adapters.repository.memory import InMemoryRepository
from leia.adapters.vector.mock import MockVectorIndex
from leia.domain.models import DocumentStatus, RawUpload, content_type_for
from leia.service import LeiaService


class _MemBlob:
    """BlobStore em memória (evita escrever em disco no teste)."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self.store[key] = data

    def get(self, key: str) -> bytes:
        return self.store[key]

    def url(self, key: str) -> str:
        return f"mem://{key}"


def _service() -> tuple[LeiaService, _MemBlob]:
    blob = _MemBlob()
    service = LeiaService(
        extractor=MockExtractor(),
        blob=blob,
        repo=InMemoryRepository(),
        vectorizer=MockVectorIndex(),
    )
    return service, blob


def test_ingest_imagem_gera_uma_pagina_e_fica_indexed() -> None:
    service, _ = _service()
    doc = service.ingest(RawUpload("foto.png", b"\x89PNG"))

    assert doc.status is DocumentStatus.INDEXED
    assert doc.page_count == 1
    assert service.get_document(doc.id).page_count == 1
    assert len(service.get_pages(doc.id)) == 1


def test_ingest_pdf_gera_multiplas_paginas() -> None:
    service, _ = _service()
    doc = service.ingest(RawUpload("contrato.pdf", b"%PDF-1.4"))

    assert doc.page_count == 3  # MockExtractor simula 3 páginas de PDF


def test_ingest_guarda_arquivo_cru_e_resultado_por_pagina_no_blob() -> None:
    service, blob = _service()
    doc = service.ingest(RawUpload("contrato.pdf", b"%PDF-1.4"))

    assert f"{doc.id}/raw/contrato.pdf" in blob.store
    assert f"{doc.id}/pages/0001.txt" in blob.store  # resultado baixável da página 1


def test_search_encontra_termo_indexado() -> None:
    service, _ = _service()
    doc = service.ingest(RawUpload("contrato.pdf", b"%PDF-1.4"))

    hits = service.search("MOCK", document_id=doc.id)
    assert hits
    assert hits[0].document_id == doc.id


def test_ingest_falha_na_extracao_marca_failed() -> None:
    class _Boom:
        def extract(
            self, upload: RawUpload, on_page: Callable[[int, int], None] | None = None
        ) -> list[str]:
            raise RuntimeError("extração explodiu")

    blob = _MemBlob()
    repo = InMemoryRepository()
    service = LeiaService(
        extractor=_Boom(), blob=blob, repo=repo, vectorizer=MockVectorIndex()
    )

    with pytest.raises(RuntimeError):
        service.ingest(RawUpload("x.pdf", b"%PDF"))

    doc = service.list_documents()[0]
    assert doc.status is DocumentStatus.FAILED


def test_content_type_for() -> None:
    assert content_type_for("PDF") == "application/pdf"
    assert content_type_for("jpg") == "image/jpeg"
    assert content_type_for("desconhecido") == "application/octet-stream"
