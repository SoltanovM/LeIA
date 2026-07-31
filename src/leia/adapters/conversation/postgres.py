"""ADAPTER driven - conversas no Postgres (tabelas `conversations` e `chat_messages`).

No mesmo banco do repo/pgvector. Conversas são POR USUÁRIO (owner) - base pra isolamento
por usuário e pra memória entre conversas (Stage 5). `init_schema()` é idempotente.
"""

from __future__ import annotations

from uuid import uuid4

import psycopg

from leia.config import get_settings
from leia.domain.models import ChatMessage, Conversation


class PostgresConversationStore:
    """Implementação de `ConversationStore` sobre o Postgres."""

    def __init__(self) -> None:
        self._dsn = get_settings().database_url

    def _connect(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn)

    def init_schema(self) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id         text PRIMARY KEY,
                    owner      text NOT NULL,
                    title      text NOT NULL DEFAULT '',
                    created_at timestamptz NOT NULL DEFAULT now()
                )
                """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id              bigserial PRIMARY KEY,
                    conversation_id text NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
                    role            text NOT NULL,
                    content         text NOT NULL,
                    created_at      timestamptz NOT NULL DEFAULT now()
                )
                """)
            cur.execute(
                "CREATE INDEX IF NOT EXISTS chat_messages_conv_idx"
                " ON chat_messages (conversation_id, id)"
            )
            conn.commit()

    def create(self, owner: str, title: str) -> Conversation:
        conversation = Conversation(id=uuid4().hex, owner=owner, title=title)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (id, owner, title) VALUES (%s, %s, %s)",
                (conversation.id, conversation.owner, conversation.title),
            )
            conn.commit()
        return conversation

    def list_by_owner(self, owner: str) -> list[Conversation]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, owner, title FROM conversations WHERE owner = %s ORDER BY created_at DESC",
                (owner,),
            )
            rows = cur.fetchall()
        return [Conversation(id=r[0], owner=r[1], title=r[2]) for r in rows]

    def get(self, conversation_id: str) -> Conversation | None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT id, owner, title FROM conversations WHERE id = %s", (conversation_id,)
            )
            row = cur.fetchone()
        return Conversation(id=row[0], owner=row[1], title=row[2]) if row else None

    def set_title(self, conversation_id: str, title: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "UPDATE conversations SET title = %s WHERE id = %s", (title, conversation_id)
            )
            conn.commit()

    def delete(self, conversation_id: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM conversations WHERE id = %s", (conversation_id,))
            conn.commit()

    def add_message(self, conversation_id: str, role: str, content: str) -> None:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO chat_messages (conversation_id, role, content) VALUES (%s, %s, %s)",
                (conversation_id, role, content),
            )
            conn.commit()

    def messages(self, conversation_id: str) -> list[ChatMessage]:
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT role, content FROM chat_messages WHERE conversation_id = %s ORDER BY id",
                (conversation_id,),
            )
            rows = cur.fetchall()
        return [ChatMessage(role=r[0], content=r[1]) for r in rows]
