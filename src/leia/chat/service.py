"""CASO DE USO do chat - orquestra as conversas (e, na Stage 3, o agente).

Depende só do port `ConversationStore`. Por enquanto o `send` persiste a pergunta e devolve
uma resposta placeholder; na Stage 3 o `answerer` (agente LangGraph consumindo o MCP) entra
no lugar do placeholder, sem mudar a UI nem a persistência.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from leia.domain.models import ChatMessage, Conversation
from leia.ports import ConversationMemory, ConversationStore

logger = logging.getLogger("leia.chat")

# Assinatura do agente (Stage 3): (pergunta, histórico) -> resposta.
Answerer = Callable[[str, "list[ChatMessage]"], str]
# Titulador (Stage 4): (primeira pergunta) -> título curto da conversa.
Titler = Callable[[str], str]

_PLACEHOLDER = "🤖 (o agente entra na Stage 3 - sua pergunta já foi salva na conversa.)"


@dataclass
class ChatService:
    """Fachada do chat, usada pela UI."""

    conversations: ConversationStore
    answerer: Answerer | None = None
    titler: Titler | None = None
    memory: ConversationMemory | None = None

    def new_conversation(self, owner: str, title: str = "Nova conversa") -> Conversation:
        return self.conversations.create(owner, title)

    def list_by_owner(self, owner: str) -> list[Conversation]:
        return self.conversations.list_by_owner(owner)

    def get(self, conversation_id: str) -> Conversation | None:
        return self.conversations.get(conversation_id)

    def messages(self, conversation_id: str) -> list[ChatMessage]:
        return self.conversations.messages(conversation_id)

    def send(self, conversation_id: str, user_text: str) -> ChatMessage:
        """Persiste a pergunta, gera a resposta e persiste. Na 1ª mensagem, nomeia a conversa."""
        history = self.conversations.messages(conversation_id)
        is_first = len(history) == 0
        self.conversations.add_message(conversation_id, "user", user_text)
        if self.answerer is not None:
            answer = self.answerer(user_text, history)
        else:
            answer = _PLACEHOLDER
        self.conversations.add_message(conversation_id, "assistant", answer)
        if is_first:
            self.conversations.set_title(conversation_id, self._make_title(user_text))
        if self.memory is not None:
            conversation = self.conversations.get(conversation_id)
            owner = conversation.owner if conversation is not None else ""
            try:
                self.memory.remember(
                    owner, conversation_id, f"Pergunta: {user_text}\nResposta: {answer}"
                )
            except Exception:  # memória entre conversas nunca deve derrubar o envio
                logger.warning("indexação da conversa (memória) falhou", exc_info=True)
        return ChatMessage(role="assistant", content=answer)

    def _make_title(self, question: str) -> str:
        """Título pela 1ª pergunta - agente de titulação, com heurística no fallback."""
        if self.titler is not None:
            try:
                title = self.titler(question).strip()
                if title:
                    return title[:60]
            except Exception:  # titular nunca deve derrubar o envio da mensagem
                logger.warning("titulação falhou; usando heurística", exc_info=True)
        first_line = next((ln for ln in question.strip().splitlines() if ln.strip()), "")
        return (first_line[:40] + "…") if len(first_line) > 40 else (first_line or "Nova conversa")

    def rename(self, conversation_id: str, title: str) -> None:
        self.conversations.set_title(conversation_id, title)

    def delete(self, conversation_id: str) -> None:
        self.conversations.delete(conversation_id)
