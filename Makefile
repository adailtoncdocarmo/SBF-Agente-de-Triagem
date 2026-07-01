# ============================================================
# Makefile — atalhos do projeto
#   make install   instala deps (pip + npm)
#   make build     gera o frontend/dist (build de produção)
#   make run       sobe o app (FastAPI servindo o dist) em :8000
#   make dev       backend com reload (:8000) + Vite dev (:5173)
#   make docker    docker compose up --build
#   make test      roda os testes (pytest)
#   make clean     remove dist, node_modules, __pycache__ e *.db
# ============================================================

PY  ?= python3
PIP ?= pip3

.PHONY: install build run dev dev-backend dev-frontend docker test clean

install:
	$(PIP) install -r backend/requirements.txt
	cd frontend && npm install

build:
	cd frontend && npm install && npm run build

run:
	$(PY) -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000

dev-backend:
	$(PY) -m uvicorn app.main:app --app-dir backend --reload --port 8000

dev-frontend:
	cd frontend && npm run dev

dev:
	@echo "Backend -> http://localhost:8000   |   Frontend (dev) -> http://localhost:5173"
	@trap 'kill 0' INT TERM EXIT; \
	$(PY) -m uvicorn app.main:app --app-dir backend --reload --port 8000 & \
	( cd frontend && npm run dev ) & \
	wait

docker:
	docker compose up --build

test:
	cd backend && $(PY) -m pytest -v

clean:
	rm -rf frontend/dist frontend/node_modules backend/data/*.db
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
