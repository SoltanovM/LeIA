"""CASO DE USO do chat — orquestra as conversas (e, na Stage 3, o agente).

Depende só do port `ConversationStore`. Por enquanto o `send` persiste a pergunta e devolve
uma resposta placeholder; na Stage 3 o `answerer` (agente LangGraph consumindo o MCP) entra
no lugar do placeholder, sem mudar a UI nem a persistência.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from leia.domain.models import ChatMessage, Conversation
from leia.ports import ConversationStore

# Assinatura do agente (injetado na Stage 3): (pergunta, histórico) -> resposta.
Answerer = Callable[[str, "list[ChatMessage]"], str]

_PLACEHOLDER = (
    "🤖 (o agente entra na Stage 3 — sua pergunta já foi salva na conversa.)"
)


@dataclass
class ChatService:
    """Fachada do chat, usada pela UI."""

    conversations: ConversationStore
    answerer: Answerer | None = None

    def new_conversation(self, owner: str, title: str = "Nova conversa") -> Conversation:
        return self.conversations.create(owner, title)

    def list_by_owner(self, owner: str) -> list[Conversation]:
        return self.conversations.list_by_owner(owner)

    def get(self, conversation_id: str) -> Conversation | None:
        return self.conversations.get(conversation_id)

    def messages(self, conversation_id: str) -> list[ChatMessage]:
        return self.conversations.messages(conversation_id)

    def send(self, conversation_id: str, user_text: str) -> ChatMessage:
        """Persiste a pergunta, gera a resposta (agente ou placeholder) e persiste também."""
        history = self.conversations.messages(conversation_id)
        self.conversations.add_message(conversation_id, "user", user_text)
        if self.answerer is not None:
            answer = self.answerer(user_text, history)
        else:
            answer = _PLACEHOLDER
        self.conversations.add_message(conversation_id, "assistant", answer)
        return ChatMessage(role="assistant", content=answer)

    def rename(self, conversation_id: str, title: str) -> None:
        self.conversations.set_title(conversation_id, title)

    def delete(self, conversation_id: str) -> None:
        self.conversations.delete(conversation_id)
