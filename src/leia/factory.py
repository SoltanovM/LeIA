"""COMPOSITION ROOT - o ÚNICO lugar que conhece os adapters concretos.

Decide QUAL conjunto de adapters injetar (por `ADAPTERS` no `.env`) e monta o `LeiaService`.
É aqui, e só aqui, que "infra encontra negócio" - o domínio continua sem saber de nada.

Imports LAZY (dentro do if): o modo `mock` sobe sem sequer importar boto3/psycopg - a UI
roda 100%% offline.
"""

from __future__ import annotations

from leia.chat.service import ChatService
from leia.config import AdapterSet, get_settings
from leia.ports import ConversationMemory
from leia.service import LeiaService


def build_conversation_memory() -> ConversationMemory:
    """Memória entre conversas (Stage 5). Usado pelo ChatService e pela tool MCP."""
    settings = get_settings()
    if settings.adapters is AdapterSet.AWS:
        from leia.adapters.conversation_memory.pgvector import PgVectorConversationMemory

        memory = PgVectorConversationMemory()
        memory.init_schema()
        return memory

    from leia.adapters.conversation_memory.mock import InMemoryConversationMemory

    return InMemoryConversationMemory()


def build_service() -> LeiaService:
    """Monta o service com o conjunto de adapters escolhido por configuração."""
    settings = get_settings()

    if settings.adapters is AdapterSet.AWS:
        from leia.adapters.blob.s3 import S3BlobStore
        from leia.adapters.extraction.bedrock import BedrockExtractor
        from leia.adapters.repository.postgres import PostgresRepository
        from leia.adapters.vector.pgvector import PgVectorIndex

        repo = PostgresRepository()
        vectorizer = PgVectorIndex()
        # Garante o schema no 1º uso (idempotente) - evita "relation does not exist"
        # quando o Postgres sobe zerado. O `make db-init` continua valendo p/ init explícito.
        repo.init_schema()
        vectorizer.init_schema()

        return LeiaService(
            extractor=BedrockExtractor(),
            blob=S3BlobStore(),
            repo=repo,
            vectorizer=vectorizer,
        )

    from leia.adapters.blob.filesystem import FilesystemBlobStore
    from leia.adapters.extraction.mock import MockExtractor
    from leia.adapters.repository.memory import InMemoryRepository
    from leia.adapters.vector.mock import MockVectorIndex

    return LeiaService(
        extractor=MockExtractor(),
        blob=FilesystemBlobStore(),
        repo=InMemoryRepository(),
        vectorizer=MockVectorIndex(),
    )


def build_chat_service() -> ChatService:
    """Monta o `ChatService` com o store de conversas do conjunto de adapters escolhido.

    Na Stage 3 este é o ponto onde o `answerer` (agente LangGraph via MCP) será injetado.
    """
    settings = get_settings()

    if settings.adapters is AdapterSet.AWS:
        from leia.adapters.conversation.postgres import PostgresConversationStore
        from leia.agent.document_agent import DocumentAgent
        from leia.agent.titler import BedrockTitler

        store = PostgresConversationStore()
        store.init_schema()
        # answerer = agente LangGraph (Claude via MCP); titler = titulação; memory = memória entre conversas.
        return ChatService(
            conversations=store,
            answerer=DocumentAgent().answer,
            titler=BedrockTitler(),
            memory=build_conversation_memory(),
        )

    from leia.adapters.conversation.memory import InMemoryConversationStore

    return ChatService(
        conversations=InMemoryConversationStore(),
        memory=build_conversation_memory(),
    )
