"""DRIVING ADAPTER — servidor MCP (Model Context Protocol).

Uma "casca" sobre o `LeiaService`: um cliente MCP (Claude Desktop, Claude Code, ...)
descobre e chama estas tools. É só mais um driving adapter — mesmo status do Streamlit;
o núcleo não muda nada.

Transporte: **Streamable HTTP** por padrão (serviço de rede em MCP_HOST:MCP_PORT/mcp,
consumido pelo agente LangGraph na Stage 3). Pra stdio (ex.: Claude Desktop), defina
MCP_TRANSPORT=stdio.

Rodar (HTTP):    uv run leia-mcp           (ou: make mcp)  -> http://localhost:8087/mcp
Inspecionar:     uv run mcp dev src/leia/mcp/server.py

Obs.: no backend=mock o repositório é em memória (por processo) — este servidor não vê os
documentos que a UI ingeriu. Use backend=aws (Postgres) pra compartilhar estado.
"""

from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from leia.config import get_settings
from leia.factory import build_service

_settings = get_settings()
mcp = FastMCP("leia", host=_settings.mcp_host, port=_settings.mcp_port)
_service = build_service()


@mcp.tool()
def list_documents() -> list[dict[str, Any]]:
    """Lista os documentos ingeridos (id, filename, page_count, status)."""
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
def total_pages(document_id: str) -> int | None:
    """Número total de páginas de um documento (None se não existir)."""
    doc = _service.get_document(document_id)
    return doc.page_count if doc is not None else None


@mcp.tool()
def page_content(document_id: str, page_number: int) -> str | None:
    """Conteúdo (texto) de uma página específica (None se não existir)."""
    page = _service.get_page(document_id, page_number)
    return page.content if page is not None else None


@mcp.tool()
def search_pages(
    query: str, k: int = 5, document_id: str | None = None
) -> list[dict[str, Any]]:
    """Busca semântica nas páginas indexadas; devolve os k trechos mais relevantes."""
    return [
        {
            "document_id": hit.document_id,
            "page_number": hit.page_number,
            "content": hit.content,
            "score": hit.score,
        }
        for hit in _service.search(query, k=k, document_id=document_id)
    ]


def main() -> None:
    """Entry point do console script `leia-mcp`.

    Default: Streamable HTTP (serviço de rede). MCP_TRANSPORT=stdio pra clientes locais.
    """
    transport = os.environ.get("MCP_TRANSPORT", "streamable-http")
    mcp.run(transport="stdio" if transport == "stdio" else "streamable-http")


if __name__ == "__main__":
    main()
