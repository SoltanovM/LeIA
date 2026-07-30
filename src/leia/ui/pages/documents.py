"""Página Documentos — upload, extração (progresso ao vivo), páginas (original × OCR) e busca."""

from __future__ import annotations

import json

import streamlit as st

from leia.domain.models import RawUpload
from leia.factory import build_service
from leia.service import LeiaService


@st.cache_resource
def _get_service() -> LeiaService:
    """Uma instância por processo (cacheada) — a factory decide os adapters."""
    return build_service()


@st.cache_data(show_spinner=False)
def _page_image(doc_id: str, number: int, content_type: str, _raw: bytes) -> bytes | None:
    """Renderiza a página `number` do original como PNG, pra comparar com o OCR.

    Imagem (PNG/JPG) = 1 página, devolve os próprios bytes. PDF = renderiza via PyMuPDF.
    `_raw` tem underscore pro cache_data NÃO hashear os bytes (chave = doc/number/tipo).
    """
    if content_type.startswith("image/"):
        return _raw if number == 1 else None
    if content_type == "application/pdf":
        try:
            import fitz
        except ImportError:
            return None
        pdf = fitz.open(stream=_raw, filetype="pdf")
        if number - 1 >= pdf.page_count:
            return None
        pix = pdf[number - 1].get_pixmap(matrix=fitz.Matrix(2, 2))
        return pix.tobytes("png")
    return None


def _sidebar_upload(service: LeiaService) -> str | None:
    """Sidebar: upload + processar (progresso ao vivo) + seletor. Retorna o id selecionado."""
    with st.sidebar:
        st.divider()
        st.header("Enviar documento")
        uploaded = st.file_uploader("PDF, PNG ou JPG", type=["pdf", "png", "jpg", "jpeg"])
        if uploaded is not None and st.button("Processar", type="primary"):
            with st.status(f"Processando {uploaded.name}…", expanded=True) as status:
                bar = st.progress(0)

                def on_progress(msg: str, frac: float | None = None) -> None:
                    st.write(f"• {msg}")
                    if frac is not None:
                        bar.progress(min(int(frac * 100), 100))

                try:
                    doc = service.ingest(
                        RawUpload(filename=uploaded.name, data=uploaded.getvalue()),
                        on_progress=on_progress,
                    )
                except Exception as exc:  # noqa: BLE001 — mostra o erro pro usuário na UI
                    status.update(label="Falha ao processar", state="error")
                    st.error(f"Erro: {exc}")
                    st.toast("❌ Falha ao processar o documento.", icon="❌")
                else:
                    bar.progress(100)
                    status.update(
                        label=f"Concluído — {doc.page_count} página(s)", state="complete"
                    )
                    st.toast(
                        f"✅ '{doc.filename}' processado: {doc.page_count} página(s).", icon="✅"
                    )

        st.divider()
        documents = service.list_documents()
        st.subheader(f"📚 Documentos processados ({len(documents)})")
        if not documents:
            st.caption("Nenhum documento ainda.")
            return None
        labels = {d.id: f"{d.filename} — {d.page_count}p · {d.status}" for d in documents}
        return st.radio(
            "Selecione um documento",
            [d.id for d in documents],
            format_func=lambda i: labels.get(i, i),
            label_visibility="collapsed",
        )


def render() -> None:
    service = _get_service()
    st.title("📄 Documentos — extração & busca")
    selected = _sidebar_upload(service)
    if not selected:
        st.info("Envie um documento na barra lateral para começar.")
        return

    tab_pages, tab_search = st.tabs(["📄 Páginas", "🔎 Busca"])

    with tab_pages:
        pages = service.get_pages(selected)
        doc = service.get_document(selected)
        original = service.get_original(selected)  # (bytes, content_type) | None

        export = {
            "document_id": selected,
            "filename": doc.filename if doc is not None else None,
            "page_count": len(pages),
            "pages": [{"number": p.number, "content": p.content} for p in pages],
        }
        st.download_button(
            "⬇️ Baixar todas as páginas (JSON)",
            data=json.dumps(export, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"{selected}.json",
            mime="application/json",
            type="primary",
        )

        # Cada página = um expander com original × OCR lado a lado (sem preview duplicado).
        for page in pages:
            img = (
                _page_image(selected, page.number, original[1], original[0])
                if original is not None
                else None
            )
            with st.expander(f"Página {page.number} — original × OCR"):
                col_o, col_t = st.columns(2)
                with col_o:
                    st.caption("📄 Original")
                    if img is not None:
                        st.image(img, use_container_width=True)
                    else:
                        st.caption("_(sem preview do original)_")
                with col_t:
                    st.caption("🔤 OCR (texto extraído)")
                    st.code(page.content or "(página vazia)", language=None)
                st.download_button(
                    "Baixar OCR desta página (.txt)",
                    data=(page.content or "").encode("utf-8"),
                    file_name=f"{selected}-p{page.number:04d}.txt",
                    key=f"dl-{page.number}",
                )

    with tab_search:
        query = st.text_input("Pergunta ou termo")
        if query:
            hits = service.search(query, k=5, document_id=selected)
            if not hits:
                st.warning("Nenhum trecho relevante encontrado.")
            for rank, hit in enumerate(hits, start=1):
                with st.container(border=True):
                    col_score, col_text = st.columns([1, 5])
                    with col_score:
                        st.metric(f"#{rank}", f"{hit.score:.3f}")
                        st.caption(f"página {hit.page_number}")
                    with col_text:
                        st.code(hit.content, language=None)
