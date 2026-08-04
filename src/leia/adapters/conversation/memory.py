"""ADAPTER driven (offline) - conversas em memória. Default do ADAPTERS=mock (por processo)."""

from __future__ import annotations

from uuid import uuid4

from leia.domain.models import ChatMessage, Conversation


class InMemoryConversationStore:
    """Guarda conversas e mensagens em dicionários no processo."""

    def __init__(self) -> None:
        self._convs: dict[str, Conversation] = {}
        self._msgs: dict[str, list[ChatMessage]] = {}

    def create(self, owner: str, title: str) -> Conversation:
        conversation = Conversation(id=uuid4().hex, owner=owner, title=title)
        self._convs[conversation.id] = conversation
        self._msgs[conversation.id] = []
        return conversation

    def list_by_owner(self, owner: str) -> list[Conversation]:
        # dict preserva ordem de inserção -> inverte pra "mais recentes primeiro".
        return [c for c in reversed(self._convs.values()) if c.owner == owner]

    def get(self, conversation_id: str) -> Conversation | None:
        return self._convs.get(conversation_id)

    def set_title(self, conversation_id: str, title: str) -> None:
        conversation = self._convs.get(conversation_id)
        if conversation is not None:
            conversation.title = title

    def delete(self, conversation_id: str) -> None:
        self._convs.pop(conversation_id, None)
        self._msgs.pop(conversation_id, None)

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        self._msgs.setdefault(conversation_id, []).append(ChatMessage(role=role, content=content))

    def messages(self, conversation_id: str) -> list[ChatMessage]:
        return list(self._msgs.get(conversation_id, []))
