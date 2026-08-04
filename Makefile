# Makefile - atalhos do LeIA.
# Rode `make` (ou `make help`) pra ver os comandos.
#
# Um docker-compose.yml (leia + postgres + frpc atrás do profile `tunnel`):
#   • test:  docker compose up            → leia + postgres em localhost:$(LEIA_PORT), SEM túnel.
#   • up:    docker compose --profile tunnel up  → + frpc (público via relay).

# Lê o .env (se existir) só pra mostrar a porta certa nas mensagens. Não falha se faltar.
-include .env
LEIA_PORT ?= 8086

.DEFAULT_GOAL := help
.PHONY: help install run run-aws lint format typecheck pytest check \
        db db-init mcp test test-stop test-logs up up-obs down restart logs ps remove build clean \
        obs obs-stop

help:  ## Lista os comandos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(firstword $(MAKEFILE_LIST)) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

# --- Desenvolvimento (sem Docker) -------------------------------------------

install:  ## Cria o venv e instala deps + projeto (editável)
	uv sync

run:  ## Sobe a UI Streamlit local via uv (adapters do .env; default mock)
	uv run leia

run-aws:  ## Sobe a UI forçando ADAPTERS=aws (precisa de AWS + Postgres no ar)
	ADAPTERS=aws uv run leia

mcp:  ## Sobe o servidor MCP (stdio) - tools do LeIA
	uv run leia-mcp

# --- Banco (Postgres/pgvector) ----------------------------------------------

db:  ## Sobe só o Postgres (dev local, ADAPTERS=aws sem Docker do app)
	docker compose up -d postgres
	@echo "→ Postgres em localhost:5432 (user/db: leia)"

db-init:  ## Cria o schema (documents, pages, page_chunks + índice HNSW)
	uv run leia-db

# --- Qualidade (learnings 06) -----------------------------------------------

lint:  ## Lint com ruff
	uv run ruff check src tests

format:  ## Formata o código com ruff
	uv run ruff format src tests

typecheck:  ## Checagem de tipos com mypy
	uv run mypy

pytest:  ## Roda os testes de unidade (domínio, sem AWS)
	uv run pytest -q

check: lint typecheck pytest  ## lint + mypy + testes (rode antes de commitar)

# --- Teste local em Docker (SÓ o leia, SEM túnel) ---------------------------

test: remove  ## Sobe SÓ o leia em Docker local, sem frpc (detached)
	docker compose up --build -d --remove-orphans
	@echo "→ LeIA no ar: http://localhost:$(LEIA_PORT)  (sem túnel)"

test-stop:  ## Para o app de teste local
	docker compose down

test-logs:  ## Segue os logs do leia (teste local)
	docker compose logs -f leia

# --- Deploy real: leia + frpc (túnel reverso pro relay) ---------------------

up:  ## Deploy: leia + frpc (túnel). Exige ADAPTERS=aws e ./.env com FRP_TOKEN.
	@[ -f .env ] || { echo "ERRO: falta ./.env (cp .env.example .env e preencha)"; exit 1; }
	@[ "$(ADAPTERS)" = "aws" ] || { echo "ERRO: deploy exige ADAPTERS=aws no .env (atual: '$(ADAPTERS)'). Mock NÃO vai pra produção."; exit 1; }
	@[ -n "$(FRP_TOKEN)" ] || { echo "ERRO: FRP_TOKEN vazio no .env (necessário pro túnel)."; exit 1; }
	@$(MAKE) --no-print-directory remove
	docker compose --profile tunnel up --build -d --remove-orphans
	@echo "→ Deploy no ar: https://LeIA.lab.soltanov.io  (via túnel frpc)"

up-obs:  ## Deploy + painel Langfuse público (obs.leia.lab.soltanov.io). Exige FRP_OBS_REMOTE_PORT.
	@[ -f .env ] || { echo "ERRO: falta ./.env (cp .env.example .env e preencha)"; exit 1; }
	@[ "$(ADAPTERS)" = "aws" ] || { echo "ERRO: deploy exige ADAPTERS=aws no .env (atual: '$(ADAPTERS)')."; exit 1; }
	@[ -n "$(FRP_TOKEN)" ] || { echo "ERRO: FRP_TOKEN vazio no .env (necessário pro túnel)."; exit 1; }
	@[ -n "$(FRP_OBS_REMOTE_PORT)" ] || { echo "ERRO: FRP_OBS_REMOTE_PORT vazio no .env (porta do obs no relay)."; exit 1; }
	@$(MAKE) --no-print-directory remove
	docker compose --profile tunnel --profile langfuse up --build -d --remove-orphans
	@echo "→ App:  https://LeIA.lab.soltanov.io"
	@echo "→ Obs:  https://obs.leia.lab.soltanov.io  (Langfuse; 1º boot demora ~1-2min)"

down:  ## Para o deployment (leia + frpc + langfuse, se no ar)
	docker compose --profile tunnel --profile langfuse down

restart: down up  ## Recria o deployment

# --- Observabilidade (tracing do agente) ------------------------------------

obs:  ## Sobe o Langfuse (obs. de LLM) + o app → UI http://localhost:3000. Lembre: OTEL_ENABLED=true
	docker compose --profile langfuse up -d
	@echo "→ Langfuse subindo (1º boot demora ~1-2min: migrações). UI: http://localhost:3000"
	@echo "  Ligue o tracing com OTEL_ENABLED=true no .env e reinicie o 'leia'."

obs-stop:  ## Para o stack do Langfuse (mantém os volumes/dados)
	docker compose --profile langfuse down

logs:  ## Segue os logs do frpc ("login to server success" = túnel ok)
	docker compose logs -f frpc

ps:  ## Estado dos containers (leia + leia-frpc)
	docker compose --profile tunnel ps

remove:  ## rm -f por nome (resolve "container name already in use")
	@for c in leia leia-mcp leia-frpc leia-postgres \
		leia-langfuse-web leia-langfuse-worker leia-langfuse-postgres \
		leia-langfuse-clickhouse leia-langfuse-redis leia-langfuse-minio; do \
		docker rm -f $$c >/dev/null 2>&1 && echo "removido: $$c" || true; \
	done
	@echo "OK (ignorados os que não existiam)"

# --- Utilitários ------------------------------------------------------------

build:  ## Builda a imagem Docker
	docker compose build

clean:  ## Remove caches de build/teste
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist src/*.egg-info
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
