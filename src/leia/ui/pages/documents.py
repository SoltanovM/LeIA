"""Página Documentos - upload, extração (progresso ao vivo), páginas (original × OCR) e busca."""

from __future__ import annotations

import json
import time

import streamlit as st

from leia.domain.models import RawUpload
from leia.factory import build_service
from leia.service import LeiaService

# Cor do status (badge) - pra categorizar de bate-olho na lista.
_STATUS_COLOR = {
    "INDEXED": "green",
    "EXTRACTED": "blue",
    "UPLOADED": "gray",
    "EXTRACTING": "orange",
    "INDEXING": "orange",
    "FAILED": "red",
}


def _status_badge(status: str) -> str:
    """Status como badge colorido (markdown do Streamlit)."""
    return f":{_STATUS_COLOR.get(status, 'gray')}-background[{status}]"


def _fmt_eta(seconds: float) -> str:
    """Segundos -> texto curto (ex.: '45s', '2m10s', '1h05m')."""
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}h{minutes:02d}m"
    return f"{minutes}m{secs:02d}s" if minutes else f"{secs}s"


def _stage_of(msg: str) -> tuple[str, str, str, str]:
    """Etapa do fluxo de ingestão -> (chave, ícone, cor, rótulo). Cada fase, uma cor.

    Deriva da mensagem que o `service` emite (recebimento → extração → salvar → indexar →
    concluído). A `chave` serve pra detectar a TROCA de etapa (e cronometrar cada uma). Cai
    no default (recebimento) se não casar - degrada com elegância.
    """
    m = msg.lower()
    if "indexando" in m:
        return "index", "🧠", "green", "Indexação (RAG)"  # vetorização
    if "salvando" in m:
        return "save", "💾", "orange", "Salvando páginas"  # grava resultado por página
    if "extraindo" in m or "página" in m or "extraída" in m:
        return "extract", "🔍", "violet", "Extração"  # multimodal (o grosso do tempo)
    if "concluído" in m:
        return "done", "✅", "green", "Concluído"
    return "receive", "📥", "blue", "Recebimento"  # guardando o arquivo (início)


@st.cache_resource
def _get_service() -> LeiaService:
    """Uma instância por processo (cacheada) - a factory decide os adapters."""
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
        st.header("Carregar documento")
        uploaded = st.file_uploader("PDF, PNG ou JPG", type=["pdf", "png", "jpg", "jpeg"])
        if uploaded is not None and st.button("Processar", type="primary"):
            # `st.status` já é recolhível; e a linha de passo é SOBRESCRITA (st.empty), então
            # a sidebar não cresce mesmo num PDF de centenas de páginas (não acumula linhas).
            with st.status(f"Processando {uploaded.name}…", expanded=True) as status:
                # A extração roda junto com esta tela (síncrona) - trocar de página a interrompe.
                st.warning(
                    "Não troque de página até terminar: a extração roda junto com esta tela e "
                    "seria interrompida (o documento ficaria incompleto).",
                    icon="⚠️",
                )
                col_bar, col_eta = st.columns([3, 1], vertical_alignment="center")
                bar = col_bar.progress(0)
                eta_box = col_eta.empty()
                stages_box = st.empty()  # histórico das etapas concluídas (com duração)
                step = st.empty()  # passo atual (sobrescrito)
                started = time.monotonic()

                # Estado (mutável, capturado pela closure) da etapa em andamento.
                done_lines: list[str] = []
                cur = {"key": "", "icon": "", "color": "", "label": ""}
                cur_start = [started]

                def _finish_stage(now: float) -> None:
                    """Fecha a etapa atual: registra a duração dela no histórico."""
                    if cur["key"]:
                        secs = now - cur_start[0]
                        done_lines.append(
                            f"{cur['icon']} :{cur['color']}[{cur['label']}] · {_fmt_eta(secs)}"
                        )
                        stages_box.markdown("  \n".join(done_lines))

                def on_progress(msg: str, frac: float | None = None) -> None:
                    key, icon, color, label = _stage_of(msg)
                    now = time.monotonic()
                    if key != cur["key"]:  # trocou de etapa -> cronometra a anterior
                        _finish_stage(now)
                        cur.update(key=key, icon=icon, color=color, label=label)
                        cur_start[0] = now
                    step.markdown(f"{icon} :{color}[{msg}]")  # sobrescreve -> só o passo atual
                    if frac is not None:
                        bar.progress(min(int(frac * 100), 100))
                        # ETA = tempo decorrido projetado no que falta (só depois de "aquecer",
                        # senão as 1ras páginas dão uma estimativa doida).
                        elapsed = now - started
                        if frac >= 0.05:
                            eta_box.caption(f"⏱️ ~{_fmt_eta(elapsed * (1 - frac) / frac)}")
                        else:
                            eta_box.caption("⏱️ …")

                try:
                    doc = service.ingest(
                        RawUpload(filename=uploaded.name, data=uploaded.getvalue()),
                        on_progress=on_progress,
                    )
                except Exception as exc:  # noqa: BLE001 - mostra o erro pro usuário na UI
                    eta_box.empty()
                    status.update(label="Falha ao processar", state="error")
                    st.error(f"Erro: {exc}")
                    st.toast("❌ Falha ao processar o documento.", icon="❌")
                else:
                    bar.progress(100)
                    total_secs = time.monotonic() - started
                    eta_box.caption(f"✅ {_fmt_eta(total_secs)}")  # tempo total gasto
                    status.update(label=f"Concluído - {doc.page_count} página(s)", state="complete")
                    st.toast(
                        f"✅ '{doc.filename}' processado: {doc.page_count} página(s).", icon="✅"
                    )

        st.divider()
        documents = service.list_documents()  # só os ATIVOS
        st.subheader(f"📚 Documentos processados ({len(documents)})")
        selected: str | None = None
        if not documents:
            st.caption("Nenhum documento ativo ainda.")
        else:
            labels = {
                d.id: f"{d.filename} · {d.page_count}p · {_status_badge(str(d.status))}"
                for d in documents
            }
            selected = st.radio(
                "Selecione um documento",
                [d.id for d in documents],
                format_func=lambda i: labels.get(i, i),
                label_visibility="collapsed",
            )

        _archived_section(service)
        return selected


def _archived_section(service: LeiaService) -> None:
    """Lista os arquivados (fora do chat/busca) com botão de desarquivar - sem reprocessar."""
    archived = [d for d in service.list_documents(include_archived=True) if d.archived]
    if not archived:
        return
    with st.expander(f"🗄️ Arquivados ({len(archived)})"):
        st.caption("Fora do chat e da busca. Os dados continuam salvos - desarquive pra usar.")
        for d in archived:
            col_name, col_unarch, col_del = st.columns([3, 1, 1], vertical_alignment="center")
            col_name.markdown(f"{d.filename}  \n:gray[{d.page_count}p]")
            if col_unarch.button("♻️", key=f"unarch-{d.id}", help="Desarquivar"):
                service.unarchive_document(d.id)
                st.toast(f"♻️ '{d.filename}' desarquivado.", icon="♻️")
                st.rerun()
            # Exclusão é destrutiva -> popover de confirmação (evita apagar por engano).
            with col_del.popover("🗑️", help="Excluir definitivamente"):
                st.markdown(f"Excluir **{d.filename}** e **todos** os dados (páginas, vetores)?")
                st.caption("Não dá pra desfazer. Precisaria reprocessar o documento do zero.")
                if st.button("Excluir definitivamente", key=f"del-{d.id}", type="primary"):
                    service.delete_document(d.id)
                    st.toast(f"🗑️ '{d.filename}' excluído.", icon="🗑️")
                    st.rerun()


def render() -> None:
    service = _get_service()
    st.title("📄 Documentos - extração & busca")
    selected = _sidebar_upload(service)
    if not selected:
        st.info("Envie um documento na barra lateral para começar.")
        return

    tab_pages, tab_search = st.tabs(["📄 Páginas", "🔎 Busca semântica"])

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
        col_dl, col_arch = st.columns([2, 1])
        with col_dl:
            st.download_button(
                "⬇️ Baixar todas as páginas (JSON)",
                data=json.dumps(export, ensure_ascii=False, indent=2).encode("utf-8"),
                file_name=f"{selected}.json",
                mime="application/json",
                type="primary",
                width="stretch",
            )
        with col_arch:
            if st.button(
                "🗄️ Arquivar",
                width="stretch",
                help="Tira do chat e da busca sem apagar os dados. Reversível a qualquer momento.",
            ):
                service.archive_document(selected)
                st.toast("🗄️ Documento arquivado (fora do chat/busca).", icon="🗄️")
                st.rerun()

        # Cada página = um expander com original × OCR lado a lado (sem preview duplicado).
        for page in pages:
            img = (
                _page_image(selected, page.number, original[1], original[0])
                if original is not None
                else None
            )
            with st.expander(f"Página {page.number} - original × OCR"):
                col_o, col_t = st.columns(2)
                with col_o:
                    st.caption("📄 Original")
                    if img is not None:
                        st.image(img, width="stretch")
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
