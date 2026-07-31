"""DRIVING ADAPTER - servidor MCP (Model Context Protocol).

Uma "casca" sobre o `LeiaService`: um cliente MCP (Claude Desktop, Claude Code, ...)
descobre e chama estas tools. É só mais um driving adapter - mesmo status do Streamlit;
o núcleo não muda nada.

Transporte: **Streamable HTTP** por padrão (serviço de rede em MCP_HOST:MCP_PORT/mcp,
consumido pelo agente LangGraph na Stage 3). Pra stdio (ex.: Claude Desktop), defina
MCP_TRANSPORT=stdio.

Rodar (HTTP):    uv run leia-mcp           (ou: make mcp)  -> http://localhost:8087/mcp
Inspecionar:     uv run mcp dev src/leia/mcp/server.py

Obs.: no backend=mock o repositório é em memória (por processo) - este servidor não vê os
documentos que a UI ingeriu. Use backend=aws (Postgres) pra compartilhar estado.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from leia.config import get_settings
from leia.factory import build_conversation_memory, build_service
from leia.logging_setup import setup_logging

setup_logging()
logger = logging.getLogger("leia.mcp")

_settings = get_settings()
mcp = FastMCP("leia", host=_settings.mcp_host, port=_settings.mcp_port)
_service = build_service()
_memory = build_conversation_memory()


@mcp.tool()
def list_documents() -> list[dict[str, Any]]:
    """Lista os documentos ingeridos (id, filename, page_count, status)."""
    logger.info("tool list_documents()")
    return [
        {
            "id": doc.id,
            "filename": doc.filename,
            "page_count": doc.page_count,
            "status": str(doc.status),
        }
        for doc in _service.list_documents()
    ]


@mcp.tool()
def find_documents(name: str, k: int = 3) -> list[dict[str, Any]]:
    """Documentos com nome PARECIDO com `name` - use pra sugerir 'você quis dizer X?'."""
    logger.info("tool find_documents(name=%r, k=%d)", name, k)
    return [
        {"filename": doc.filename, "document_id": doc.id}
        for doc in _service.suggest_documents(name, k=k)
    ]


@mcp.tool()
def total_pages(document_id: str) -> int | None:
    """Número total de páginas de um documento (aceita id OU nome do arquivo)."""
    doc_id = _service.resolve_document(document_id)
    doc = _service.get_document(doc_id) if doc_id else None
    return doc.page_count if doc is not None else None


@mcp.tool()
def page_content(document_id: str, page_number: int) -> str | None:
    """Conteúdo (texto) de uma página (aceita id OU nome do arquivo). None se não existir."""
    doc_id = _service.resolve_document(document_id)
    logger.info("tool page_content(doc=%r -> %r, page=%d)", document_id, doc_id, page_number)
    page = _service.get_page(doc_id, page_number) if doc_id else None
    return page.content if page is not None else None


@mcp.tool()
def search_pages(query: str, k: int = 5, document_id: str | None = None) -> list[dict[str, Any]]:
    """Busca semântica nas páginas indexadas; devolve os k trechos mais relevantes.

    Cada trecho traz `filename` e `page_number` - USE-OS pra citar a fonte (não o id/hash).
    """
    logger.info("tool search_pages(query=%r, k=%d, document_id=%r)", query, k, document_id)
    doc_id = _service.resolve_document(document_id) if document_id else None
    # id -> nome do arquivo (inclui arquivados, caso a busca seja direcionada a um deles).
    names = {d.id: d.filename for d in _service.list_documents(include_archived=True)}
    return [
        {
            "document_id": hit.document_id,
            "filename": names.get(hit.document_id, hit.document_id),
            "page_number": hit.page_number,
            "content": hit.content,
            "score": hit.score,
        }
        for hit in _service.search(query, k=k, document_id=doc_id)
    ]


@mcp.tool()
def search_conversations(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Busca em conversas ANTERIORES do usuário trechos relevantes (memória entre conversas).

    Use quando a pergunta puder se apoiar no que já foi conversado antes.
    """
    logger.info("tool search_conversations(query=%r, k=%d)", query, k)
    return [
        {"conversation_id": hit.conversation_id, "content": hit.content, "score": hit.score}
        for hit in _memory.recall(query, k=k)
    ]


def main() -> None:
    """Entry point do console script `leia-mcp`.

    Default: Streamable HTTP (serviço de rede). MCP_TRANSPORT=stdio pra clientes locais.
    """
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    mcp.run(transport="stdio" if transport == "stdio" else "streamable-http")


if __name__ == "__main__":
    main()
