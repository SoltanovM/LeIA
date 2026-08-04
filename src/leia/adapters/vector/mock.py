"""ADAPTER driven (offline) - busca por palavra-chave em memória. Default do ADAPTERS=mock.

Não é embedding de verdade: pontua por ocorrência dos termos. Serve pra rodar a busca sem
AWS/Postgres. O adapter pgvector faz a busca semântica real.
"""

from __future__ import annotations

from leia.domain.models import Page, SearchHit


class MockVectorIndex:
    """Guarda as páginas indexadas no processo e busca por contagem de termos."""

    def __init__(self) -> None:
        self._pages: list[Page] = []

    def index(self, document_id: str, pages: list[Page]) -> int:
        self._pages = [p for p in self._pages if p.document_id != document_id]
        self._pages.extend(pages)
        return len(pages)

    def delete(self, document_id: str) -> None:
        self._pages = [p for p in self._pages if p.document_id != document_id]

    def search(self, query: str, k: int = 5, document_id: str | None = None) -> list[SearchHit]:
        terms = [t for t in query.lower().split() if t]
        hits: list[SearchHit] = []
        for page in self._pages:
            if document_id is not None and page.document_id != document_id:
                continue
            text = page.content.lower()
            score = sum(text.count(term) for term in terms)
            if score > 0:
                hits.append(
                    SearchHit(page.document_id, page.number, page.content[:500], float(score))
                )
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
