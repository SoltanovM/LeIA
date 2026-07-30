"""Página Chat (principal) — conversas estilo ChatGPT.

Stage 1: cria conversas, persiste mensagens e mostra o histórico. A resposta ainda é um
placeholder; na Stage 3 o agente LangGraph (via MCP) entra no lugar, sem mudar esta UI.
"""

from __future__ import annotations

import streamlit as st

from leia.chat.service import ChatService
from leia.factory import build_chat_service


@st.cache_resource
def _chat_service() -> ChatService:
    return build_chat_service()


def render() -> None:
    user = st.session_state.get("user", "")
    chat = _chat_service()

    with st.sidebar:
        st.divider()
        if st.button("➕ Nova conversa", type="primary", use_container_width=True):
            conversation = chat.new_conversation(user)
            st.session_state["conv_id"] = conversation.id
            st.rerun()
        st.caption("Conversas")
        for conversation in chat.list_by_owner(user):
            label = conversation.title or "(sem título)"
            if st.button(label, key=f"conv-{conversation.id}", use_container_width=True):
                st.session_state["conv_id"] = conversation.id
                st.rerun()

    st.title("💬 Chat")
    conv_id = st.session_state.get("conv_id")
    if not conv_id or chat.get(conv_id) is None:
        st.info("Crie uma **nova conversa** na barra lateral para começar.")
        return

    for message in chat.messages(conv_id):
        with st.chat_message(message.role):
            st.markdown(message.content)

    if prompt := st.chat_input("Pergunte algo sobre seus documentos…"):
        chat.send(conv_id, prompt)
        st.rerun()
