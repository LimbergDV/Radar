# Comandos shortcuts del backend. Todos asumen el venv de la RAIZ del repo:
#   cd /Users/limberg/Documents/Estadia_Neurotry/Radar && source .venv/bin/activate
#
# Por que los --reload-exclude: uvicorn vigila todo backend/, y ahi puede haber
# un .venv propio (167 MB, ~2500 archivos .py). Sin excluirlo, cualquier
# `pip install` reinicia la API y watchfiles rehashea todo el arbol.

PY      := python
VENV    := ../.venv/bin
UVICORN := $(VENV)/uvicorn
ALEMBIC := $(VENV)/alembic
PYTEST  := $(VENV)/pytest

# OJO: las rutas deben ser ABSOLUTAS. Uvicorn/watchfiles reporta los cambios con
# ruta absoluta, asi que un `--reload-exclude .venv` relativo NO hace nada (se
# compara `.venv` contra `/ruta/absoluta/.venv/...` y nunca coincide).
EXCLUDES := --reload-exclude "$(CURDIR)/.venv" \
            --reload-exclude "$(CURDIR)/__pycache__" \
            --reload-exclude "$(CURDIR)/alembic" \
            --reload-exclude "$(CURDIR)/tests" \
            --reload-exclude '*.log'

.PHONY: help install dev run worker test test-unit test-integration migrate migration downgrade

help:
	@echo "Backend NewsRadar — comandos disponibles:"
	@echo "  make install         Instala las dependencias en el venv de la raiz"
	@echo "  make dev             Servidor con autoreload (recomendado para desarrollar)"
	@echo "  make run             Servidor sin autoreload (como en produccion)"
	@echo "  make test            Tests unitarios (no necesita BD)"
	@echo "  make test-integration Tests completos, requiere PostgreSQL"
	@echo "  make migrate         Aplica las migraciones de Alembic"
	@echo "  make migration       Crea una migracion nueva (make migration m='mensaje')"

install:
	$(VENV)/pip install -r requirements.txt

dev:
	$(UVICORN) main:app $(EXCLUDES) --reload --port 8000

run:
	$(UVICORN) main:app --host 0.0.0.0 --port 8000

test:
	$(PYTEST) tests/ -q -v

test-unit:
	$(PYTEST) tests/ -q --ignore=tests/test_integration.py

test-integration:
	RUN_DB_TESTS=1 $(PYTEST) tests/ -q

migrate:
	$(ALEMBIC) upgrade head

migration:
	$(ALEMBIC) revision --autogenerate -m "$(m)"

downgrade:
	$(ALEMBIC) downgrade -1