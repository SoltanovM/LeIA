# 📄 LeIA

Plataforma de **documentos**: envie um PDF, PNG ou JPG e o LeIA **extrai o conteúdo página
a página** (baixável), **persiste**, **vetoriza** pra busca semântica e expõe **MCP tools**.
A extração usa **Amazon Bedrock** multimodal (Converse) — sem OCR à parte.

> **Nome:** *LeIA* = "leia!" (imperativo de ler) + **IA**. 🙂
> Aplicação prática dos `../learnings-matheus` (hexagonal, uv/packaging, pydantic-settings, Bedrock, RAG, MCP).

## Arquitetura (hexagonal — ports & adapters)

A dependência aponta sempre **pra dentro**: UI, MCP e a infra (Bedrock/S3/Postgres) dependem
do núcleo, nunca o contrário. Trocar de tecnologia = escrever outro **adapter**.

```
src/leia/
├── domain/models.py     # NÚCLEO — RawUpload, Document, Page, SearchHit, DocumentStatus
├── ports.py             # PORTS (Protocol): DocumentExtractor, BlobStore, DocumentRepository, Vectorizer
├── service.py           # LeiaService.ingest() + consultas — injeta os ports
├── adapters/
│   ├── extraction/      # mock | bedrock (Converse multimodal, 1 chamada/página)
│   ├── blob/            # filesystem | s3 (arquivo cru + resultado por página)
│   ├── repository/      # memory | postgres (documents, pages)
│   ├── vector/          # mock | pgvector (page_chunks + HNSW; embeddings Titan V2)
│   └── aws_clients.py   # clients boto3 memoizados
├── config.py            # pydantic-settings; BACKEND=mock|aws
├── factory.py           # COMPOSITION ROOT — escolhe os adapters por BACKEND
├── db.py                # init do schema Postgres (console `leia-db`)
├── ui/app.py, ui/cli.py # DRIVING — Streamlit (console `leia`)
└── mcp/server.py        # DRIVING — MCP/FastMCP (console `leia-mcp`)
tests/test_service.py    # ingest com adapters mock — SEM AWS/Postgres
```

**Prova viva de ports/adapters:** o swap `mock ↔ aws` é só a env `BACKEND` — o `service` e o
domínio não mudam uma linha. `mock` roda 100% offline; `aws` = Bedrock + S3 + Postgres/pgvector.

## Rodar

Pré-requisito: [uv](https://docs.astral.sh/uv/). Atalhos no `Makefile` (`make help`).

```bash
cp .env.example .env      # default BACKEND=mock (roda sem AWS/Postgres)
make install              # uv sync
make run                  # UI em http://localhost:8086 (modo mock)
make mcp                  # servidor MCP (stdio)
```

Modo real (Bedrock + S3 + Postgres/pgvector):

```bash
make db                   # sobe o Postgres (pgvector)
make db-init              # cria o schema (documents, pages, page_chunks)
make run-aws              # UI com BACKEND=aws (precisa de credenciais AWS)
```

Com Docker — um `docker-compose.yml` (leia + postgres + frpc atrás de um *profile*):

```bash
make test                 # leia + postgres, SEM túnel → http://localhost:8086
make test-stop            # para o teste local

make up                   # DEPLOY: + frpc (túnel reverso pro relay AWS)
make down                 # para o deployment
make logs / ps / remove   # logs do frpc / estado / limpa containers por nome
```

### Túnel (arquitetura lab.soltanov.io)

A máquina local não tem IP público. O `frpc` disca pro **relay AWS** (`frps` + Caddy), que
publica o app em `https://LeIA.lab.soltanov.io`. Padrão idêntico aos outros apps do repo
`lab.soltanov.io-apps` (proxy `type=tcp`, `remotePort` único — o **8086** é do LeIA).

Tudo que é sensível (endereço/porta do relay, token) fica no **`.env`** (git-ignored); o
`frpc.toml` é só um template com `{{ .Envs.X }}`, seguro pra versionar.

**Checklist de deploy:**
1. `cp .env.example .env` e preencha `FRP_SERVER_ADDR`, `FRP_REMOTE_PORT`, `FRP_TOKEN`
   (o token é o MESMO do `frps` no relay).
2. No **relay**, o Caddy precisa do bloco `LeIA.lab.soltanov.io → 127.0.0.1:8086`
   (`systemctl reload caddy`). DNS wildcard `*.lab.soltanov.io` já cobre o subdomínio.
3. `make up` → confira `make logs` (`login to server success` + `start proxy success`).

## Qualidade

```bash
make check                # ruff + mypy + pytest
make pytest               # só os testes (núcleo, sem AWS)
```

## Próximos passos

- Validar `BACKEND=aws` ponta a ponta (Bedrock + S3 + Postgres reais).
- **FastAPI** como outro driving adapter, reaproveitando o mesmo `service`.
- Worker separado de **vetorização** (SQS/Lambda) implementando o `Vectorizer`.
- **Textract** como `DocumentExtractor` alternativo pra OCR de escaneado.
