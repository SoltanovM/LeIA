"""DRIVING ADAPTER - UI Streamlit (multipage, estilo ChatGPT). Login + navegação.

Tela de login = sem sidebar, formulário centralizado. Depois do login: navegação (Chat /
Documentos) e um rodapé de usuário FIXO no fim da sidebar. Importa o núcleo IN-PROCESS.
"""

from __future__ import annotations

import streamlit as st

from leia.config import get_settings
from leia.logging_setup import setup_logging
from leia.tracing import setup_tracing
from leia.ui.pages.about import render as about_page
from leia.ui.pages.chat import render as chat_page
from leia.ui.pages.docs import render as docs_page
from leia.ui.pages.documents import render as documents_page

st.set_page_config(page_title="LeIA", page_icon="📄", layout="wide")
setup_logging()  # logs leia.* -> stdout (docker logs)
setup_tracing()  # OTel: instrumenta o agente -> Langfuse

# CSS: some com a sidebar (login) e fixa o rodapé no fundo (depois do login).
_HIDE_SIDEBAR = "<style>[data-testid='stSidebar']{display:none;}</style>"
_PIN_FOOTER = """
<style>
[data-testid="stSidebar"] > div:first-child { height: 100vh; }
[data-testid="stSidebarUserContent"] {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}
.st-key-sidebar_footer {
    margin-top: auto;
    padding-bottom: 1rem;
}
</style>
"""


def _require_login() -> str:
    """Tela de login (sem sidebar, centralizada). Bloqueia o app até autenticar."""
    if not st.session_state.get("auth_user"):
        st.markdown(_HIDE_SIDEBAR, unsafe_allow_html=True)
        settings = get_settings()
        _, center, _ = st.columns([1, 1.3, 1])
        with center:
            st.markdown("<h1 style='text-align:center'>📄 LeIA</h1>", unsafe_allow_html=True)
            st.markdown(
                "<p style='text-align:center;color:gray'>Entre para acessar seus documentos"
                " e o chat.</p>",
                unsafe_allow_html=True,
            )
            with st.form("login"):
                user = st.text_input("Usuário", placeholder="usuário")
                pwd = st.text_input("Senha", type="password", placeholder="••••••••")
                entrar = st.form_submit_button("Entrar", type="primary", width="stretch")
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
st.markdown(_PIN_FOOTER, unsafe_allow_html=True)

navigation = st.navigation(
    [
        st.Page(chat_page, title="Chat", icon="💬", url_path="chat", default=True),
        st.Page(documents_page, title="Documentos", icon="📄", url_path="documentos"),
        st.Page(docs_page, title="Sobre o app", icon="📚", url_path="sobre-o-app"),
        st.Page(about_page, title="Sobre mim", icon="🧑‍💻", url_path="sobre-mim"),
    ]
)
navigation.run()
