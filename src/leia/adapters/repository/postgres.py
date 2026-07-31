"""ADAPTER driven - repositório no Postgres (tabelas `documents` e `pages`).

Metadados/manifesto e o texto de cada página. Fica no MESMO Postgres do pgvector
(um banco só pra metadado + vetor). `init_schema()` é idempotente (rode no `make db-init`).
"""

from __future__ import annotations

import psycopg

from leia.config import get_settings
from leia.domain.models import Document, DocumentStatus, Page


class PostgresRepository:
    """Implementação de `DocumentRepository` sobre o Postgres."""

    def __init__(self) -> None:
        self._dsn = get_settings().database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def init_schema(self) -> None:
        """Cria as tabelas (idempotente)."""
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id           text PRIMARY KEY,
                    filename     text NOT NULL,
                    content_type text NOT NULL,
                    page_count   int  NOT NULL DEFAULT 0,
                    status       text NOT NULL,
                    archived     boolean NOT NULL DEFAULT false
                )
                """)
            # Migração idempotente pra bancos antigos (antes da coluna archived existir).
            cur.execute(
                "ALTER TABLE documents ADD COLUMN IF NOT EXISTS archived"
                " boolean NOT NULL DEFAULT false"
            )
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pages (
                    document_id text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    number      int  NOT NULL,
                    content     text NOT NULL,
                    PRIMARY KEY (document_id, number)
                )
                """)
            conn.commit()

    def save_document(self, document: Document) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (id, filename, content_type, page_count, status, archived)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    filename = EXCLUDED.filename,
                    content_type = EXCLUDED.content_type,
                    page_count = EXCLUDED.page_count,
                    status = EXCLUDED.status,
                    archived = EXCLUDED.archived
                """,
                (
                    document.id,
                    document.filename,
                    document.content_type,
                    document.page_count,
                    str(document.status),
                    document.archived,
                ),
            )
            conn.commit()

    def get_document(self, document_id: str) -> Document | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, filename, content_type, page_count, status, archived"
                " FROM documents WHERE id = %s",
                (document_id,),
            )
            row = cur.fetchone()
        return _to_document(row) if row else None

    def list_documents(self, include_archived: bool = False) -> list[Document]:
        clause = "" if include_archived else " WHERE archived = false"
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, filename, content_type, page_count, status, archived"
                f" FROM documents{clause} ORDER BY id"
            )
            rows = cur.fetchall()
        return [_to_document(row) for row in rows]

    def set_archived(self, document_id: str, archived: bool) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("UPDATE documents SET archived = %s WHERE id = %s", (archived, document_id))
            conn.commit()

    def delete_document(self, document_id: str) -> None:
        # As páginas somem junto pelo ON DELETE CASCADE da FK (ver init_schema).
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
            conn.commit()

    def save_pages(self, pages: list[Page]) -> None:
        if not pages:
            return
        document_id = pages[0].document_id
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM pages WHERE document_id = %s", (document_id,))
            for page in pages:
                cur.execute(
                    "INSERT INTO pages (document_id, number, content) VALUES (%s, %s, %s)",
                    (page.document_id, page.number, page.content),
                )
            conn.commit()

    def get_page(self, document_id: str, number: int) -> Page | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT document_id, number, content FROM pages WHERE document_id = %s AND number = %s",
                (document_id, number),
            )
            row = cur.fetchone()
        return Page(row[0], row[1], row[2]) if row else None

    def get_pages(self, document_id: str) -> list[Page]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT document_id, number, content FROM pages WHERE document_id = %s ORDER BY number",
                (document_id,),
            )
            rows = cur.fetchall()
        return [Page(row[0], row[1], row[2]) for row in rows]


def _to_document(row: tuple) -> Document:
    return Document(
        id=row[0],
        filename=row[1],
        content_type=row[2],
        page_count=row[3],
        status=DocumentStatus(row[4]),
        archived=row[5],
    )
