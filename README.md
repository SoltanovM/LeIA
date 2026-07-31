# 📄 LeIA

Plataforma de **documentos com IA**: envie um PDF, PNG ou JPG e o LeIA **extrai o conteúdo
página a página** (Amazon Bedrock multimodal, sem OCR à parte), **persiste**, **vetoriza**
(RAG/pgvector) e permite **busca semântica** + um **chat** (estilo ChatGPT) cujo **agente**
consome **MCP tools** e responde fundamentado nos seus documentos, **citando as fontes**
(arquivo/página).

> **Nome:** *LeIA* = "leia!" (imperativo de ler) + **IA**. 🙂
> Arquitetura **hexagonal** (ports & adapters). Backend `mock` (offline) ou `aws` (Bedrock +
> S3 + Postgres/pgvector) - troca por uma env var.

## Arquitetura (hexagonal - ports & adapters)

A dependência aponta sempre **pra dentro**: UI, MCP e a infra (Bedrock/S3/Postgres) dependem
do núcleo, nunca o contrário. Trocar de tecnologia = escrever outro **adapter**.

```md
src/leia/
├── domain/models.py     # NÚCLEO - RawUpload, Document, Page, SearchHit, ChatMessage, Conversation
├── ports.py             # PORTS: DocumentExtractor, BlobStore, DocumentRepository, Vectorizer,
│                        #        ConversationStore, ConversationMemory
├── service.py           # LeiaService - ingest() + consultas (progresso por etapa/página, arquivar, excluir)
├── chat/service.py      # ChatService - conversas; o agente entra como `answerer`
├── agent/               # agente LangGraph (create_agent) + titulação automática da conversa
├── adapters/
│   ├── extraction/      # mock | bedrock  (Converse multimodal, 1 chamada/página, paralelo + retry)
│   ├── blob/            # filesystem | s3  (arquivo cru + resultado por página)
│   ├── repository/      # memory | postgres  (documents, pages)
│   ├── vector/          # mock | pgvector  (page_chunks + HNSW; embeddings Titan V2)
│   ├── conversation/    # memory | postgres  (conversations, chat_messages)
│   ├── conversation_memory/  # mock | pgvector  (memória semântica ENTRE conversas)
│   └── aws_clients.py   # clients boto3 memoizados
├── config.py            # pydantic-settings - BACKEND, login, MCP, Bedrock, Postgres, observabilidade
├── factory.py           # COMPOSITION ROOT - build_service() / build_chat_service()
├── tracing.py           # OpenTelemetry (OpenInference) -> Langfuse (liga com OTEL_ENABLED)
├── db.py                # init do schema Postgres (console `leia-db`)
├── ui/
│   ├── app.py           # DRIVING - login + navegação multipage (console `leia`)
│   └── pages/           # chat.py (principal) | documents.py | about.py | docs.py ("Sobre o app")
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

A UI tem **login** (usuário default no `.env`: `AUTH_USER` / `AUTH_PASSWORD`) e as páginas:
**💬 Chat** (principal, agente que cita as fontes), **📄 Documentos** (upload com progresso ao
vivo - barra, ETA e duração por etapa; original × OCR lado a lado; busca; **arquivar** e
**excluir**) e **📚 Sobre o app** / **🧑‍💻 Sobre mim**.

Documentos **arquivados** saem do chat/busca sem apagar nada (reversível); **excluir** apaga de
vez tudo relacionado (vetores, blobs, páginas, metadados).

Modo real (Bedrock + S3 + Postgres/pgvector):

```bash
make db                   # sobe o Postgres (pgvector)
make db-init              # cria o schema (documents, pages, page_chunks, conversations, chat_messages, …)
make run-aws              # UI com BACKEND=aws (precisa de credenciais AWS)
```

Com Docker - um `docker-compose.yml` (leia + leia-mcp + postgres, mais Langfuse e frpc sob profiles):

```bash
make test                 # sobe leia + leia-mcp + postgres → http://localhost:8086 (SEM túnel)
make test-stop            # para o teste local
```

### Extração (Bedrock)

Cada página é **1 chamada** `converse` (multimodal). As páginas são transcritas **em paralelo**
(`EXTRACTION_MAX_WORKERS`, I/O-bound) e cada chamada **retenta** erros transitórios do Bedrock
(`ModelError`/`Throttling`/5xx) com backoff exponencial (`EXTRACTION_MAX_RETRIES`).

### MCP (Model Context Protocol)

O `leia-mcp` expõe as capacidades do LeIA como **tools** sobre o mesmo núcleo - é só mais um
*driving adapter*. Tools: `list_documents`, `find_documents`, `total_pages`, `page_content`,
`search_pages`, `search_conversations`. Roda em **Streamable HTTP** por padrão
(`MCP_HOST:MCP_PORT/mcp`); pra stdio (ex.: Claude Desktop), `MCP_TRANSPORT=stdio`. O agente do
chat consome esse servidor via `MCP_URL` (`langchain-mcp-adapters`).

### Observabilidade (OpenTelemetry → Langfuse)

O código é instrumentado com **OpenTelemetry** (via **OpenInference**): cada chamada de LLM,
tool e passo do agente vira um *span*, exportado por **OTLP** pro **Langfuse** self-hosted (UI
de LLM: prompts, tool-calls, tokens, custo, latência, raciocínio do agente).

```bash
make obs                  # sobe o stack do Langfuse (UI http://localhost:3000)
# depois: OTEL_ENABLED=true no .env e reinicie o leia
make obs-stop             # para o Langfuse (mantém os dados nos volumes)
```

## Deploy (túnel reverso)

A máquina local não tem IP público: um cliente **frp** (`frpc`) disca *pra fora* até um **relay
na AWS** (frps + Caddy), que publica o app com HTTPS - sem abrir porta na rede local.

```bash
make up                   # DEPLOY: leia + frpc (túnel) → https://LeIA.lab.soltanov.io
make up-obs               # DEPLOY + painel Langfuse público → https://obs.leia.lab.soltanov.io
make down                 # para o deployment
make logs / ps / remove   # logs do frpc / estado / limpa containers por nome
```

Exige `BACKEND=aws` e `FRP_TOKEN` no `.env` (mock não vai pra produção). Nada sensível vai pro
git: o `frpc.toml` lê tudo via `{{ .Envs.X }}` do `.env` (git-ignored).

## Qualidade

```bash
make check                # ruff + mypy + pytest
make pytest               # só os testes (núcleo + chat, sem AWS/Postgres)
```

## Próximos passos

- **Worker assíncrono:** hoje a extração roda síncrona ao *run* do Streamlit (navegar durante o
  processamento a interrompe). Próximo passo: upload **enfileira** → **worker** processa →
  UI faz *polling* do status. Em nível cloud: **fila (SQS/EventBridge) + worker (ECS/Lambda)**.
- **FastAPI** como outro driving adapter, reaproveitando o mesmo `service`.
- **CI/CD** (GitHub Actions) + **IaC** (Terraform) + deploy serverless (ECS/Fargate ou Lambda).
- **Textract** como `DocumentExtractor` alternativo pra OCR de escaneado.
