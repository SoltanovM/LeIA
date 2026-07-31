"""DOMÍNIO - tipos puros da plataforma de documentos (sem infra, sem AWS).

Fluxo dos dados:
    RawUpload  (arquivo cru que o usuário subiu)
        -> extração por página ->
    Document + [Page]   (metadados + conteúdo de cada página, persistidos)
        -> vetorização ->
    SearchHit   (trecho relevante devolvido pela busca semântica)

Nada aqui conhece Bedrock/S3/Postgres - é o núcleo que os adapters servem. Regra de ouro do
hexagonal: a dependência aponta de fora PRA DENTRO (infra depende do domínio, nunca o contrário).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

# Extensão -> content-type (usado ao guardar o arquivo cru no blob store).
_CONTENT_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "txt": "text/plain",
}


def content_type_for(extension: str) -> str:
    """content-type a partir da extensão (default binário genérico)."""
    return _CONTENT_TYPES.get(extension.lower(), "application/octet-stream")


class DocumentStatus(StrEnum):
    """Ciclo de vida de um documento na plataforma."""

    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    INDEXING = "INDEXING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class RawUpload:
    """Arquivo cru recém-enviado (ainda não extraído)."""

    filename: str
    data: bytes

    @property
    def extension(self) -> str:
        return self.filename.rsplit(".", 1)[-1].lower() if "." in self.filename else ""


@dataclass(frozen=True)
class Page:
    """Uma página extraída (conteúdo em texto). `number` é 1-based."""

    document_id: str
    number: int
    content: str


@dataclass
class Document:
    """Metadados/manifesto de um documento (o conteúdo mora nas Pages/blob).

    `archived=True` tira o documento do fluxo ATIVO (chat/busca) sem apagar nada - os dados
    (páginas, blob, vetores) continuam lá. É reversível: desarquivar traz de volta na hora,
    sem reprocessar. Serve pra "limpar" a lista de processados guardando pra uso futuro.
    """

    id: str
    filename: str
    content_type: str
    page_count: int = 0
    status: DocumentStatus = DocumentStatus.UPLOADED
    archived: bool = False


@dataclass(frozen=True)
class SearchHit:
    """Trecho relevante devolvido pela busca semântica (RAG)."""

    document_id: str
    page_number: int
    content: str
    score: float


@dataclass(frozen=True)
class ChatMessage:
    """Uma fala do chat. `role` = 'user' | 'assistant'."""

    role: str
    content: str


@dataclass
class Conversation:
    """Uma conversa do chat (pertence a um usuário). `title` é auto-gerado depois."""

    id: str
    owner: str
    title: str


@dataclass(frozen=True)
class MemoryHit:
    """Trecho relevante de uma conversa ANTERIOR (memória entre conversas)."""

    conversation_id: str
    content: str
    score: float
