# LeIA - imagem do app Streamlit. Usa uv (mesmo tooling do projeto) pra instalar deps.
FROM python:3.12-slim

# uv: gerenciador de pacotes rápido, copiado do binário oficial (sem pip install extra).
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Instala as dependências primeiro: cache de layer - só reinstala se requirements mudar.
COPY requirements.txt .
RUN uv pip install --system -r requirements.txt

# Copia o código do app.
COPY app.py .
COPY leia ./leia

# Porta padrão (sobrescrita pelo .env / compose via LEIA_PORT).
ENV LEIA_PORT=8086
EXPOSE 8086

# --server.address 0.0.0.0 = aceita conexões de fora do container.
# --server.headless true   = não tenta abrir navegador nem pedir e-mail no 1º uso.
# Forma shell (sem colchetes) pra que ${LEIA_PORT} seja expandido pelo shell.
CMD streamlit run app.py \
    --server.port=${LEIA_PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true
