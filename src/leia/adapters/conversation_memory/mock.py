"""ADAPTER driven (offline) - memória de conversas em memória, busca por palavra-chave."""

from __future__ import annotations

from leia.domain.models import MemoryHit


class InMemoryConversationMemory:
    """Guarda as trocas no processo e recupera por contagem de termos (sem embeddings)."""

    def __init__(self) -> None:
        self._items: list[tuple[str, str]] = []  # (conversation_id, text)

    def remember(self, owner: str, conversation_id: str, text: str) -> None:
        self._items.append((conversation_id, text))

    def recall(self, query: str, k: int = 5) -> list[MemoryHit]:
        terms = [t for t in query.lower().split() if t]
        hits: list[MemoryHit] = []
        for conversation_id, text in self._items:
            low = text.lower()
            score = sum(low.count(term) for term in terms)
            if score > 0:
                hits.append(MemoryHit(conversation_id, text[:500], float(score)))
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits[:k]
