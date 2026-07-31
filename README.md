# 📄 LeIA

Plataforma de **documentos com IA**: envie um PDF, PNG ou JPG e o LeIA **extrai o conteúdo
página a página** (Amazon Bedrock multimodal, sem OCR à parte), **persiste**, **vetoriza**
(RAG/pgvector) e permite **busca semântica** + um **chat** (estilo ChatGPT) que responde
fundamentado no conteúdo dos seus documentos, via um agente que consome **MCP tools**.

> **Nome:** *LeIA* = "leia!" (imperativo de ler) + **IA**. 🙂
> Arquitetura **hexagonal** (ports & adapters). Backend `mock` (offline) ou `aws` (Bedrock +
> S3 + Postgres/pgvector) - troca por uma env var.

## Arquitetura (hexagonal - ports & adapters)

A dependência aponta sempre **pra dentro**: UI, MCP e a infra (Bedrock/S3/Postgres) dependem
do núcleo, nunca o contrário. Trocar de tecnologia = escrever outro **adapter**.

```md
src/leia/
├── domain/models.py     # NÚCLEO - RawUpload, Document, Page, SearchHit, ChatMessage, Conversation
├── ports.py             # PORTS: DocumentExtractor, BlobStore, DocumentRepository, Vectorizer, ConversationStore
├── service.py           # LeiaService.ingest() + consultas (progresso por etapa/página)
├── chat/service.py      # ChatService - conversas; o agente entra como `answerer`
├── adapters/
│   ├── extraction/      # mock | bedrock  (Converse multimodal, 1 chamada/página)
│   ├── blob/            # filesystem | s3  (arquivo cru + resultado por página)
│   ├── repository/      # memory | postgres  (documents, pages)
│   ├── vector/          # mock | pgvector  (page_chunks + HNSW; embeddings Titan V2)
│   ├── conversation/    # memory | postgres  (conversations, chat_messages)
│   └── aws_clients.py   # clients boto3 memoizados
├── config.py            # pydantic-settings - BACKEND, login, MCP, Bedrock, Postgres
├── factory.py           # COMPOSITION ROOT - build_service() / build_chat_service()
├── db.py                # init do schema Postgres (console `leia-db`)
├── ui/
│   ├── app.py           # DRIVING - login + navegação multipage (console `leia`)
│   └── pages/           # chat.py (principal, estilo ChatGPT) | documents.py
└── mcp/server.py        # DRIVING - servidor MCP em HTTP (console `leia-mcp`)
tests/                   # test_service.py, test_chat.py - com adapters mock, SEM AWS/Postgres
```

**Prova viva de ports/adapters:** o swap `mock ↔ aws` é só a env `BACKEND` - `service`, `chat`
e domínio não mudam uma linha. `mock` roda 100% offline; `aws` = Bedrock + S3 + Postgres/pgvector.

## Rodar

Pré-requisito: [uv](https://docs.astral.sh/uv/). Atalhos no `Makefile` (`make help`).

```bash
cp .env.example .env      # default BACKEND=mock (roda sem AWS/Postgres)
make install              # uv sync
make run                  # UI em http://localhost:8086 (Chat + Documentos)
make mcp                  # servidor MCP HTTP em http://localhost:8087/mcp
```

A UI tem **login** (usuário default configurável no `.env`: `AUTH_USER` / `AUTH_PASSWORD`) e
duas páginas: **💬 Chat** (principal) e **📄 Documentos** (upload com progresso ao vivo,
original × OCR lado a lado, busca).

Modo real (Bedrock + S3 + Postgres/pgvector):

```bash
make db                   # sobe o Postgres (pgvector)
make db-init              # cria o schema (documents, pages, page_chunks, conversations, chat_messages)
make run-aws              # UI com BACKEND=aws (precisa de credenciais AWS)
```

Com Docker - um `docker-compose.yml` (leia + leia-mcp + postgres):

```bash
make test                 # sobe leia + leia-mcp + postgres → http://localhost:8086
make test-stop            # para o teste local

make up                   # DEPLOY (produção): exige BACKEND=aws (mock não vai pra prod)
make down                 # para o deployment
make logs / ps / remove   # logs / estado / limpa containers por nome
```

### MCP (Model Context Protocol)

O `leia-mcp` expõe as capacidades do LeIA como **tools** (`list_documents`, `total_pages`,
`page_content`, `search_pages`) sobre o mesmo núcleo - é só mais um *driving adapter*. Roda em
**Streamable HTTP** por padrão (`MCP_HOST:MCP_PORT/mcp`); pra stdio (ex.: Claude Desktop),
`MCP_TRANSPORT=stdio`. O agente do chat consome esse servidor via `MCP_URL`.

## Qualidade

```bash
make check                # ruff + mypy + pytest
make pytest               # só os testes (núcleo + chat, sem AWS/Postgres)
```

## Próximos passos

- **Agente LangGraph** (chat) com **Claude** via Bedrock, consumindo o `leia-mcp` por
  `langchain-mcp-adapters`; título de conversa auto-gerado; memória entre conversas.
- **FastAPI** como outro driving adapter, reaproveitando o mesmo `service`.
- Worker separado de **vetorização** (SQS/EventBridge) implementando o `Vectorizer`.
- **Textract** como `DocumentExtractor` alternativo pra OCR de escaneado.
