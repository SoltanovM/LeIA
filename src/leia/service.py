"""CASO DE USO = a regra de negócio (o núcleo). Orquestra os ports, sem conhecer adapter.

`LeiaService` recebe os ports prontos (injeção de dependência) — quem os cria é a `factory`
(composition root). Nenhum import de boto3/psycopg/streamlit aqui: a dependência aponta
sempre PRA DENTRO.

Fluxo do `ingest`:  blob(cru) -> extrai páginas -> repo(páginas) -> blob(resultado/página) -> vetoriza.
Cada etapa atualiza o `status` do documento (rastreável por quem consultar).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import uuid4

from leia.domain.models import (
    Document,
    DocumentStatus,
    Page,
    RawUpload,
    SearchHit,
    content_type_for,
)
from leia.ports import BlobStore, DocumentExtractor, DocumentRepository, Vectorizer

logger = logging.getLogger("leia.ingest")

# Callback de progresso: (mensagem legível, fração 0..1 opcional).
ProgressFn = Callable[[str, "float | None"], None]


def _raw_key(document_id: str, filename: str) -> str:
    """Chave do arquivo cru no blob store."""
    return f"{document_id}/raw/{filename}"


def _page_key(document_id: str, number: int) -> str:
    """Chave do resultado (texto) de uma página no blob store (baixável)."""
    return f"{document_id}/pages/{number:04d}.txt"


@dataclass
class LeiaService:
    """Fachada do núcleo — usada pelos driving adapters (Streamlit, MCP, FastAPI)."""

    extractor: DocumentExtractor
    blob: BlobStore
    repo: DocumentRepository
    vectorizer: Vectorizer
    new_id: Callable[[], str] = field(default=lambda: uuid4().hex)

    def ingest(self, upload: RawUpload, on_progress: ProgressFn | None = None) -> Document:
        """Processa um upload de ponta a ponta e devolve o `Document` final (INDEXED).

        `on_progress(msg, frac)` (opcional) recebe cada etapa do fluxo, pra UI/logs
        acompanharem o progresso. Toda etapa também vai pro logger `leia.ingest`.
        """

        def report(message: str, fraction: float | None = None) -> None:
            logger.info(message)
            if on_progress is not None:
                on_progress(message, fraction)

        document_id = self.new_id()
        document = Document(
            id=document_id,
            filename=upload.filename,
            content_type=content_type_for(upload.extension),
            status=DocumentStatus.UPLOADED,
        )
        # 1) guarda o arquivo cru e registra o documento.
        report(f"Recebido '{upload.filename}' — guardando o arquivo…", 0.03)
        self.blob.put(_raw_key(document_id, upload.filename), upload.data, document.content_type)
        self.repo.save_document(document)

        try:
            # 2) extrai o texto de cada página (progresso página a página).
            document.status = DocumentStatus.EXTRACTING
            self.repo.save_document(document)
            report("Extraindo conteúdo…", 0.08)

            def on_page(i: int, total: int) -> None:
                report(f"Página {i}/{total} extraída", 0.08 + 0.62 * (i / total))

            texts = self.extractor.extract(upload, on_page=on_page)
            pages = [
                Page(document_id=document_id, number=i, content=text)
                for i, text in enumerate(texts, start=1)
            ]
            self.repo.save_pages(pages)

            # 3) grava o resultado de cada página no blob (download direto).
            report(f"Salvando resultado de {len(pages)} página(s)…", 0.74)
            for page in pages:
                self.blob.put(
                    _page_key(document_id, page.number),
                    page.content.encode("utf-8"),
                    "text/plain",
                )
            document.page_count = len(pages)
            document.status = DocumentStatus.EXTRACTED
            self.repo.save_document(document)

            # 4) vetoriza pra busca semântica.
            document.status = DocumentStatus.INDEXING
            self.repo.save_document(document)
            report(f"Indexando {len(pages)} página(s) para busca (RAG)…", 0.85)
            chunks = self.vectorizer.index(document_id, pages)
            document.status = DocumentStatus.INDEXED
            self.repo.save_document(document)
            report(f"Concluído: {len(pages)} página(s), {chunks} trecho(s) indexados.", 1.0)
        except Exception:
            document.status = DocumentStatus.FAILED
            self.repo.save_document(document)
            logger.exception("Falha ao processar '%s'", upload.filename)
            raise

        return document

    # --- consultas (usadas pela UI e pelas MCP tools) -------------------------

    def get_document(self, document_id: str) -> Document | None:
        return self.repo.get_document(document_id)

    def list_documents(self) -> list[Document]:
        return self.repo.list_documents()

    def get_page(self, document_id: str, number: int) -> Page | None:
        return self.repo.get_page(document_id, number)

    def get_pages(self, document_id: str) -> list[Page]:
        return self.repo.get_pages(document_id)

    def page_result_url(self, document_id: str, number: int) -> str:
        """URL/caminho pra baixar o resultado (texto) de uma página."""
        return self.blob.url(_page_key(document_id, number))

    def get_original(self, document_id: str) -> tuple[bytes, str] | None:
        """Arquivo ORIGINAL (bytes) + content_type, pra preview/comparação. None se sumiu."""
        document = self.repo.get_document(document_id)
        if document is None:
            return None
        try:
            data = self.blob.get(_raw_key(document_id, document.filename))
        except Exception:  # noqa: BLE001 — sem original = sem preview, não é erro fatal
            return None
        return data, document.content_type

    def search(self, query: str, k: int = 5, document_id: str | None = None) -> list[SearchHit]:
        return self.vectorizer.search(query, k=k, document_id=document_id)
