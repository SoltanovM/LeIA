"""Inicialização do schema do Postgres (metadados + pgvector).

Console script `leia-db` (ver pyproject / `make db-init`). Idempotente: cria as tabelas
`documents`, `pages`, `page_chunks` e o índice HNSW se ainda não existirem.
"""

from __future__ import annotations

from leia.adapters.conversation.postgres import PostgresConversationStore
from leia.adapters.conversation_memory.pgvector import PgVectorConversationMemory
from leia.adapters.repository.postgres import PostgresRepository
from leia.adapters.vector.pgvector import PgVectorIndex


def init_db() -> None:
    """Cria o schema (repo + vetor + conversas + memória). Requer o Postgres no ar."""
    PostgresRepository().init_schema()
    PgVectorIndex().init_schema()
    PostgresConversationStore().init_schema()
    PgVectorConversationMemory().init_schema()


def main() -> None:
    init_db()
    print(
        "schema pronto: documents, pages, page_chunks, conversations, chat_messages,"
        " conversation_chunks"
    )


if __name__ == "__main__":
    main()
