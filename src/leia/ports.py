"""PORTS = interfaces (contratos). O núcleo fala com o mundo externo SÓ por aqui.

Vocabulário de NEGÓCIO, sem cheiro de tecnologia: "extraia as páginas", "guarde o blob",
"indexe pra busca" - nunca "invoke o Bedrock" ou "faça INSERT no Postgres". Cada port tem
um ou mais adapters concretos (ver pacote `adapters`); trocar de tecnologia = escrever
outro adapter, sem tocar no domínio/service.

Uso `Protocol` (duck typing estrutural): qualquer classe com estes métodos "é" o port,
sem precisar herdar.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from leia.domain.models import (
    ChatMessage,
    Conversation,
    Document,
    MemoryHit,
    Page,
    RawUpload,
    SearchHit,
)


class DocumentExtractor(Protocol):
    """Extrai o conteúdo de um documento, uma string de texto por página."""

    def extract(
        self, upload: RawUpload, on_page: Callable[[int, int], None] | None = None
    ) -> list[str]:
        """Documento cru -> lista de páginas (1 string por página, na ordem).

        `on_page(i, total)`, se fornecido, é chamado após cada página extraída (progresso).
        """
        ...


class BlobStore(Protocol):
    """Armazena bytes crus (arquivo original + resultado por página baixável)."""

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def get(self, key: str) -> bytes: ...

    def url(self, key: str) -> str:
        """URL/caminho pra baixar o objeto (presigned no S3, path no filesystem)."""
        ...

    def delete_prefix(self, prefix: str) -> None:
        """Apaga TODOS os objetos sob `prefix` (ex.: '<id>/' = arquivo cru + páginas)."""
        ...


class DocumentRepository(Protocol):
    """Persiste o manifesto do documento e o texto de cada página (metadados)."""

    def save_document(self, document: Document) -> None: ...

    def get_document(self, document_id: str) -> Document | None: ...

    def list_documents(self, include_archived: bool = False) -> list[Document]:
        """Documentos. Por padrão só os ATIVOS; `include_archived=True` traz os arquivados também."""
        ...

    def set_archived(self, document_id: str, archived: bool) -> None:
        """Arquiva/desarquiva um documento (não apaga dados; é reversível)."""
        ...

    def delete_document(self, document_id: str) -> None:
        """Apaga o documento e suas páginas PERMANENTEMENTE (irreversível)."""
        ...

    def save_pages(self, pages: list[Page]) -> None: ...

    def get_page(self, document_id: str, number: int) -> Page | None: ...

    def get_pages(self, document_id: str) -> list[Page]: ...


class Vectorizer(Protocol):
    """Indexa páginas pra busca semântica (RAG) e responde consultas por similaridade."""

    def index(self, document_id: str, pages: list[Page]) -> int:
        """Indexa as páginas do documento; devolve quantos trechos foram gravados."""
        ...

    def delete(self, document_id: str) -> None:
        """Remove do índice todos os trechos do documento."""
        ...

    def search(self, query: str, k: int = 5, document_id: str | None = None) -> list[SearchHit]:
        """Os k trechos mais relevantes pra `query` (opcionalmente dentro de 1 documento)."""
        ...


class ConversationStore(Protocol):
    """Persiste as conversas do chat e suas mensagens (por usuário)."""

    def create(self, owner: str, title: str) -> Conversation: ...

    def list_by_owner(self, owner: str) -> list[Conversation]:
        """Conversas do usuário, mais recentes primeiro."""
        ...

    def get(self, conversation_id: str) -> Conversation | None: ...

    def set_title(self, conversation_id: str, title: str) -> None: ...

    def delete(self, conversation_id: str) -> None: ...

    def add_message(self, conversation_id: str, role: str, content: str) -> None: ...

    def messages(self, conversation_id: str) -> list[ChatMessage]:
        """Mensagens da conversa, em ordem cronológica."""
        ...


class ConversationMemory(Protocol):
    """Memória semântica ENTRE conversas: guarda trocas e recupera as relevantes (RAG)."""

    def remember(self, owner: str, conversation_id: str, text: str) -> None: ...

    def recall(self, query: str, k: int = 5) -> list[MemoryHit]:
        """Os k trechos de conversas anteriores mais relevantes pra `query`."""
        ...
