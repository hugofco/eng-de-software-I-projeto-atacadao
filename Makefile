# Atalhos de desenvolvimento (Linux/macOS/WSL). No Windows sem make, use os comandos do README.
PY ?= python3
VENV := .venv
BIN := $(VENV)/bin
MANAGE := $(BIN)/python manage.py

.PHONY: help setup venv install migrations migrate seed run test check docker-up docker-down clean

help:
	@echo "make setup       -> venv + dependências + migrações + dados de demonstração"
	@echo "make run         -> servidor de desenvolvimento em http://127.0.0.1:8000"
	@echo "make test        -> suíte de testes"
	@echo "make check       -> verificações do Django"
	@echo "make docker-up   -> PostgreSQL + aplicação via Docker Compose"
	@echo "make clean       -> remove venv, SQLite e caches"

setup: install migrate seed
	@echo ""
	@echo "Pronto. Rode 'make run' e acesse http://127.0.0.1:8000"
	@echo "Logins de demonstração: G001 (gerente), F001 (funcionário), C001 (comprador) / senha demo1234"

venv:
	$(PY) -m venv $(VENV)

install: venv
	$(BIN)/pip install --upgrade pip
	$(BIN)/pip install -r requirements.txt

# Gera as migrações caso ainda não existam (e as atualiza se os modelos mudarem).
# Depois da 1ª execução, versione apps/*/migrations/0*.py no git.
migrations:
	$(MANAGE) makemigrations --noinput

migrate: migrations
	$(MANAGE) migrate --noinput

seed:
	$(MANAGE) seed_demo

run:
	$(MANAGE) runserver

test: migrations
	$(MANAGE) test --verbosity 2

check: migrations
	$(MANAGE) check

docker-up:
	docker compose up --build

docker-down:
	docker compose down -v

clean:
	rm -rf $(VENV) db.sqlite3 staticfiles
	find . -name "__pycache__" -type d -prune -exec rm -rf {} +
