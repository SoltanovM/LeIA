"""ADAPTER driven (offline) - repositório em memória. Default do ADAPTERS=mock.

Vive só enquanto o processo roda (não compartilha entre UI e MCP). Bom pra dev/test;
em produção o adapter Postgres persiste de verdade.
"""

from __future__ import annotations

from dataclasses import replace

from leia.domain.models import Document, Page


class InMemoryRepository:
    """Guarda documentos e páginas em dicionários no processo."""

    def __init__(self) -> None:
        self._docs: dict[str, Document] = {}
        self._pages: dict[str, dict[int, Page]] = {}

    def save_document(self, document: Document) -> None:
        self._docs[document.id] = replace(document)  # cópia: evita mutação externa

    def get_document(self, document_id: str) -> Document | None:
        doc = self._docs.get(document_id)
        return replace(doc) if doc is not None else None

    def list_documents(self, include_archived: bool = False) -> list[Document]:
        return [replace(doc) for doc in self._docs.values() if include_archived or not doc.archived]

    def set_archived(self, document_id: str, archived: bool) -> None:
        doc = self._docs.get(document_id)
        if doc is not None:
            doc.archived = archived

    def delete_document(self, document_id: str) -> None:
        self._docs.pop(document_id, None)
        self._pages.pop(document_id, None)

    def save_pages(self, pages: list[Page]) -> None:
        for page in pages:
            self._pages.setdefault(page.document_id, {})[page.number] = page

    def get_page(self, document_id: str, number: int) -> Page | None:
        return self._pages.get(document_id, {}).get(number)

    def get_pages(self, document_id: str) -> list[Page]:
        by_number = self._pages.get(document_id, {})
        return [by_number[n] for n in sorted(by_number)]
