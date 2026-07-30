"""DRIVING ADAPTER — UI Streamlit (multipage, estilo ChatGPT). Login + navegação.

**Chat** é a tela principal (perguntas livres ao agente); **Documentos** é a página de
upload/extração/busca. As duas importam o núcleo IN-PROCESS (sem HTTP) via factory.

Sobe com:  `leia`  (console script)  ou  `streamlit run src/leia/ui/app.py`
"""

from __future__ import annotations

import logging

import streamlit as st

from leia.config import get_settings
from leia.ui.pages.chat import render as chat_page
from leia.ui.pages.documents import render as documents_page

st.set_page_config(page_title="LeIA", page_icon="📄", layout="wide")
logging.getLogger("leia").setLevel(logging.INFO)  # progresso do ingest também vai pros logs


def _require_login() -> str:
    """Bloqueia o app até autenticar; devolve o usuário logado (guardado na sessão)."""
    if not st.session_state.get("auth_user"):
        settings = get_settings()
        st.title("🔐 LeIA — login")
        with st.form("login"):
            user = st.text_input("Usuário")
            pwd = st.text_input("Senha", type="password")
            entrar = st.form_submit_button("Entrar", type="primary")
        ok = (
            bool(settings.auth_password)
            and user == settings.auth_user
            and pwd == settings.auth_password
        )
        if entrar and ok:
            st.session_state["auth_user"] = user
            st.rerun()
        elif entrar:
            st.error("Usuário ou senha inválidos.")
        st.stop()
    return st.session_state["auth_user"]


current_user = _require_login()
st.session_state["user"] = current_user

with st.sidebar:
    st.caption(f"👤 **{current_user}**")
    if st.button("Sair", use_container_width=True):
        st.session_state.clear()
        st.rerun()

navigation = st.navigation(
    [
        st.Page(chat_page, title="Chat", icon="💬", default=True),
        st.Page(documents_page, title="Documentos", icon="📄"),
    ]
)
navigation.run()
