"""Testa o ChatService com o store de conversas em memória — SEM Postgres."""

from __future__ import annotations

from leia.adapters.conversation.memory import InMemoryConversationStore
from leia.chat.service import ChatService


def _service() -> ChatService:
    return ChatService(conversations=InMemoryConversationStore())


def test_nova_conversa_persiste_mensagens() -> None:
    chat = _service()
    conv = chat.new_conversation("matt", "Teste")

    assert conv.owner == "matt"
    reply = chat.send(conv.id, "olá?")
    assert reply.role == "assistant"

    msgs = chat.messages(conv.id)
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[0].content == "olá?"


def test_answerer_injetado_recebe_historico() -> None:
    chat = ChatService(
        conversations=InMemoryConversationStore(),
        answerer=lambda q, history: f"eco:{q} (hist={len(history)})",
    )
    conv = chat.new_conversation("matt")

    chat.send(conv.id, "primeira")
    reply = chat.send(conv.id, "segunda")

    assert reply.content.startswith("eco:segunda")
    # o answerer recebe o histórico ANTES da pergunta atual: user+assistant da 1ª troca.
    assert "hist=2" in reply.content


def test_conversas_isoladas_por_usuario() -> None:
    chat = _service()
    chat.new_conversation("matt")
    chat.new_conversation("ana")

    assert len(chat.list_by_owner("matt")) == 1
    assert len(chat.list_by_owner("ana")) == 1


def test_rename_e_delete() -> None:
    chat = _service()
    conv = chat.new_conversation("matt")

    chat.rename(conv.id, "Novo nome")
    renamed = chat.get(conv.id)
    assert renamed is not None
    assert renamed.title == "Novo nome"

    chat.delete(conv.id)
    assert chat.get(conv.id) is None
