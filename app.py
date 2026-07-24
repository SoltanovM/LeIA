"""LeIA - pergunte qualquer coisa sobre seus documentos.

Entrypoint do Streamlit. Envie um PDF, PNG ou JPG e converse com ele: por baixo, o
arquivo vai NATIVAMENTE pro modelo no Amazon Bedrock (Converse API) - sem OCR, sem
extrair texto na mão.

Rodar local:   streamlit run app.py --server.port 8086
Rodar Docker:  docker compose -f docker-compose.leia.yml up --build
"""

from __future__ import annotations

import streamlit as st

from leia.bedrock import BedrockClient
from leia.config import get_settings
from leia.documents import SUPPORTED_EXTENSIONS, to_content_block

st.set_page_config(page_title="LeIA", page_icon="📄", layout="centered")


@st.cache_resource
def get_client() -> BedrockClient:
    """Cria o client Bedrock uma vez por processo (boto3 é caro de instanciar)."""
    return BedrockClient()


# --- estado da sessão ---------------------------------------------------------
# `messages`: histórico no formato Converse (é o que enviamos ao Bedrock).
# `doc_block`: bloco de conteúdo do documento atual (document/image).
# `doc_name`: nome do arquivo atual, pra detectar troca de documento.
st.session_state.setdefault("messages", [])
st.session_state.setdefault("doc_block", None)
st.session_state.setdefault("doc_name", None)


# --- barra lateral: info + reset ---------------------------------------------
with st.sidebar:
    st.header("📄 LeIA")
    st.caption("Perguntas sobre documentos, via Amazon Bedrock.")
    settings = get_settings()
    st.write(f"**Modelo:** `{settings.bedrock_model_id}`")
    st.write(f"**Região:** `{settings.aws_region}`")
    if st.button("🗑️ Limpar conversa"):
        st.session_state.messages = []
        st.rerun()


st.title("📄 LeIA")
st.caption("Envie um documento (PDF, PNG ou JPG) e pergunte o que quiser sobre ele.")


# --- upload -------------------------------------------------------------------
uploaded = st.file_uploader(
    "Documento",
    type=SUPPORTED_EXTENSIONS,
    accept_multiple_files=False,
)

if uploaded is not None and uploaded.name != st.session_state.doc_name:
    # Documento novo -> prepara o bloco de conteúdo e zera a conversa anterior.
    st.session_state.doc_block = to_content_block(uploaded.name, uploaded.getvalue())
    st.session_state.doc_name = uploaded.name
    st.session_state.messages = []
    st.success(f"Documento carregado: **{uploaded.name}**. Pode perguntar!")


# --- histórico da conversa ----------------------------------------------------
def _render_text(content: list[dict]) -> str:
    """Extrai só as partes de texto de uma mensagem Converse (ignora document/image)."""
    return "\n".join(part["text"] for part in content if "text" in part)


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(_render_text(msg["content"]))


# --- entrada do usuário -------------------------------------------------------
question = st.chat_input("Pergunte algo sobre o documento...")

if question:
    if st.session_state.doc_block is None:
        st.warning("Envie um documento antes de perguntar.")
        st.stop()

    # A 1ª pergunta carrega o documento junto; as seguintes vão só com texto.
    if not st.session_state.messages:
        user_content = [st.session_state.doc_block, {"text": question}]
    else:
        user_content = [{"text": question}]
    st.session_state.messages.append({"role": "user", "content": user_content})

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Lendo o documento..."):
            answer = get_client().converse(st.session_state.messages)
        st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": [{"text": answer}]})
