"""ADAPTER driven - memória de conversas no Postgres/pgvector (tabela `conversation_chunks`).

Cada troca (pergunta+resposta) vira um vetor; `recall` traz as trocas anteriores mais
próximas da pergunta atual. Reaproveita o `_embed` do Vectorizer (Titan V2).
"""

from __future__ import annotations

import psycopg
from pgvector.psycopg import register_vector

from leia.adapters.vector.pgvector import _embed
from leia.config import get_settings
from leia.domain.models import MemoryHit


class PgVectorConversationMemory:
    """Implementação de `ConversationMemory` sobre Postgres/pgvector."""

    def __init__(self) -> None:
        self._dsn = get_settings().database_url

    def _connect(self) -> psycopg.Connection:
        conn = psycopg.connect(self._dsn)
        register_vector(conn)
        return conn

    def init_schema(self) -> None:
        dim = get_settings().embedding_dimensions
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS conversation_chunks (
                    id              bigserial PRIMARY KEY,
                    owner           text NOT NULL,
                    conversation_id text NOT NULL,
                    content         text NOT NULL,
                    embedding       vector({dim}) NOT NULL
                )
                """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS conversation_chunks_embedding_idx"
                " ON conversation_chunks USING hnsw (embedding vector_cosine_ops)"
            )
            conn.commit()

    def remember(self, owner: str, conversation_id: str, text: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_chunks (owner, conversation_id, content, embedding)"
                " VALUES (%s, %s, %s, %s)",
                (owner, conversation_id, text, _embed(text)),
            )
            conn.commit()

    def recall(self, query: str, k: int = 5) -> list[MemoryHit]:
        query_embedding = _embed(query)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT conversation_id, content, 1 - (embedding <=> %s::vector) AS score"
                " FROM conversation_chunks ORDER BY embedding <=> %s::vector LIMIT %s",
                (query_embedding, query_embedding, k),
            )
            rows = cur.fetchall()
        return [MemoryHit(row[0], row[1], float(row[2])) for row in rows]
