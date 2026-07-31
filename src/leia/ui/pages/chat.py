"""Página Chat (principal) - estilo ChatGPT.

Digita direto (a conversa nasce no 1º envio), spinner "digitando…", resposta em streaming,
cards de sugestão no estado inicial, avatares, e a conversa ATIVA destacada (fundo suave -
diferente do botão "Nova conversa"). Resposta = `answerer` do ChatService.
"""

from __future__ import annotations

import re
import time
from collections.abc import Iterator

import streamlit as st

from leia.chat.service import ChatService
from leia.factory import build_chat_service

_AVATARS = {"user": "🧑", "assistant": "🤖"}
_SUGGESTIONS = [
    "Resuma os documentos que eu carreguei.",
    "Quais são os pontos principais?",
    "O que diz sobre prazos e valores?",
]


@st.cache_resource
def _chat_service() -> ChatService:
    return build_chat_service()


def _stream_words(text: str) -> Iterator[str]:
    """Gera o texto em pedaços, pro efeito de digitação do `st.write_stream`."""
    for token in re.findall(r"\S+\s*", text):
        yield token
        time.sleep(0.012)


def _sidebar(chat: ChatService, user: str) -> None:
    with st.sidebar:
        if st.button("➕ Nova conversa", type="primary", width="stretch"):
            st.session_state.pop("conv_id", None)  # volta pro estado "nova conversa"
            st.rerun()
        st.caption("Conversas")

        active_id = st.session_state.get("conv_id")
        if active_id:  # destaca a conversa ativa (fundo suave + barra), diferente do primary
            st.markdown(
                "<style>.st-key-open-" + active_id + " button {"
                " background:#E0E7FF !important; border-left:3px solid #6366F1 !important;"
                " text-align:left; }</style>",
                unsafe_allow_html=True,
            )
        for conversation in chat.list_by_owner(user):
            col_open, col_menu = st.columns([5, 1])
            if col_open.button(
                conversation.title or "(sem título)",
                key=f"open-{conversation.id}",
                width="stretch",
                type="tertiary",
            ):
                st.session_state["conv_id"] = conversation.id
                st.rerun()
            with col_menu.popover("⋯", width="stretch"):
                new_title = st.text_input(
                    "Renomear", value=conversation.title, key=f"rn-{conversation.id}"
                )
                if st.button("💾 Salvar", key=f"sv-{conversation.id}", width="stretch"):
                    chat.rename(conversation.id, new_title)
                    st.rerun()
                if st.button("🗑️ Apagar", key=f"del-{conversation.id}", width="stretch"):
                    chat.delete(conversation.id)
                    if active_id == conversation.id:
                        st.session_state.pop("conv_id", None)
                    st.rerun()


def render() -> None:
    user = st.session_state.get("user", "")
    chat = _chat_service()
    _sidebar(chat, user)

    conv_id = st.session_state.get("conv_id")
    active = chat.get(conv_id) if conv_id else None

    if active is not None:
        st.title(active.title or "💬 Conversa")
        for message in chat.messages(active.id):
            with st.chat_message(message.role, avatar=_AVATARS.get(message.role)):
                st.markdown(message.content)
    else:
        st.title("💬 Nova conversa")
        st.caption("Pergunte algo sobre seus documentos - ou comece por uma sugestão:")
        for index, (col, suggestion) in enumerate(zip(st.columns(len(_SUGGESTIONS)), _SUGGESTIONS)):
            if col.button(suggestion, key=f"sugg-{index}", width="stretch"):
                st.session_state["_pending"] = suggestion
                st.rerun()

    prompt = st.chat_input("Pergunte algo sobre seus documentos…") or st.session_state.pop(
        "_pending", None
    )
    if prompt:
        if active is None:  # cria a conversa no 1º envio (estilo ChatGPT)
            conv_id = chat.new_conversation(user).id
            st.session_state["conv_id"] = conv_id
        if conv_id:
            with st.chat_message("user", avatar=_AVATARS["user"]):
                st.markdown(prompt)
            with st.chat_message("assistant", avatar=_AVATARS["assistant"]):
                with st.spinner("digitando…"):
                    reply = chat.send(conv_id, prompt)
                st.write_stream(_stream_words(reply.content))
            st.rerun()
