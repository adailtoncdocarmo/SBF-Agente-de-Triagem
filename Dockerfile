# ============================================================
# Dockerfile multi-stage
#   Estágio 1 (Node)  → builda o React em /frontend/dist
#   Estágio 2 (Python)→ copia o dist, instala o backend e sobe o uvicorn
# Resultado: uma imagem única que serve API + frontend na porta 8000.
# ============================================================

# ---------- Estágio 1: build do frontend ----------
FROM node:20-alpine AS frontend-build
WORKDIR /frontend

# Instala dependências primeiro (melhor cache de camadas)
COPY frontend/package*.json ./
RUN npm install

# Copia o código e gera o build de produção
COPY frontend/ ./
RUN npm run build


# ---------- Estágio 2: runtime Python ----------
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependências do backend (camada cacheável)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Código do backend
COPY backend/ /app/backend/

# Build do frontend vindo do estágio 1
COPY --from=frontend-build /frontend/dist /app/frontend/dist

EXPOSE 8000

# `--app-dir backend` coloca o pacote `app` no sys.path; o cwd /app é a raiz
# do repo, então config.py resolve frontend/dist e backend/data corretamente.
CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
