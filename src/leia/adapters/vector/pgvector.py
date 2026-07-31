"""ADAPTER driven - busca semântica (RAG) com Postgres + pgvector.

Fluxo: chunka cada página -> embeda com Titan V2 (Bedrock) -> grava (content + vector).
A busca embeda a query e traz os k chunks mais próximos (distância cosseno `<=>`; como o
Titan normaliza, score = 1 - distância). `init_schema()` é idempotente (`make db-init`).
"""

from __future__ import annotations

import json
from typing import Any

import psycopg
from pgvector.psycopg import register_vector

from leia.adapters.aws_clients import bedrock_runtime
from leia.config import get_settings
from leia.domain.models import Page, SearchHit


def _chunk_text(text: str, size: int = 800, overlap: int = 100) -> list[str]:
    """Quebra o texto em janelas de ~`size` chars com sobreposição (evita cortar ideias)."""
    text = text.strip()
    if not text:
        return []
    step = max(1, size - overlap)
    chunks = (text[i : i + size].strip() for i in range(0, len(text), step))
    return [chunk for chunk in chunks if chunk]


def _embed(text: str) -> list[float]:
    """Texto -> vetor de `embedding_dimensions` floats (Titan V2, normalizado)."""
    settings = get_settings()
    body = json.dumps(
        {"inputText": text, "dimensions": settings.embedding_dimensions, "normalize": True}
    )
    resp = bedrock_runtime().invoke_model(modelId=settings.bedrock_embedding_model_id, body=body)
    return json.loads(resp["body"].read())["embedding"]  # type: ignore[no-any-return]


class PgVectorIndex:
    """Implementação de `Vectorizer` sobre Postgres/pgvector."""

    def __init__(self) -> None:
        self._dsn = get_settings().database_url

    def _connect(self) -> psycopg.Connection:
        conn = psycopg.connect(self._dsn)
        register_vector(conn)  # deixa passar list[float] como vector
        return conn

    def init_schema(self) -> None:
        """Cria a extensão, a tabela de chunks e o índice HNSW (idempotente).

        Conecta SEM `register_vector` de propósito: registrar o tipo `vector` exige que a
        extensão já exista - e é exatamente ela que criamos aqui (ovo-e-galinha). Como o
        init só roda DDL (não faz bind de vetor), a conexão crua basta.
        """
        dim = get_settings().embedding_dimensions
        with psycopg.connect(self._dsn) as conn, conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS page_chunks (
                    id          bigserial PRIMARY KEY,
                    document_id text NOT NULL,
                    page_number int  NOT NULL,
                    chunk_index int  NOT NULL,
                    content     text NOT NULL,
                    embedding   vector({dim}) NOT NULL
                )
                """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS page_chunks_embedding_idx
                ON page_chunks USING hnsw (embedding vector_cosine_ops)
                """)
            conn.commit()

    def index(self, document_id: str, pages: list[Page]) -> int:
        count = 0
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM page_chunks WHERE document_id = %s", (document_id,))
            for page in pages:
                for chunk_index, chunk in enumerate(_chunk_text(page.content)):
                    cur.execute(
                        "INSERT INTO page_chunks"
                        " (document_id, page_number, chunk_index, content, embedding)"
                        " VALUES (%s, %s, %s, %s, %s)",
                        (document_id, page.number, chunk_index, chunk, _embed(chunk)),
                    )
                    count += 1
            conn.commit()
        return count

    def search(self, query: str, k: int = 5, document_id: str | None = None) -> list[SearchHit]:
        query_embedding = _embed(query)
        sql = (
            "SELECT document_id, page_number, content, 1 - (embedding <=> %s::vector) AS score"
            " FROM page_chunks"
        )
        params: list[Any] = [query_embedding]
        if document_id is not None:
            sql += " WHERE document_id = %s"
            params.append(document_id)
        sql += " ORDER BY embedding <=> %s::vector LIMIT %s"
        params += [query_embedding, k]

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return [SearchHit(row[0], row[1], row[2], float(row[3])) for row in rows]
