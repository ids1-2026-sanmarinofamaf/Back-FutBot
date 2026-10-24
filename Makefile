.PHONY: help install setup up down down-v reset-db clean migrate migration seed run db-shell logs test test-fast test-lf test-cov test-game test-api check

PYTHON ?= python3
PYTEST ?= pytest

help:
	@echo "========================================================================"
	@echo "                        FutBot Backend Makefile                        "
	@echo "========================================================================"
	@echo "Entorno y Puesta en marcha:"
	@echo "  make setup                    Setup inicial (crea .env si falta, levanta DB, migra y siembra)"
	@echo "  make install                  Instala las dependencias de Python"
	@echo "  make run                      Levanta Postgres, migra y corre la API con reload"
	@echo ""
	@echo "Base de datos y Docker:"
	@echo "  make up                       Levanta Postgres y espera a que esté listo"
	@echo "  make down                     Frena Postgres (los datos se conservan)"
	@echo "  make down-v                   Frena Postgres y BORRA volumen de datos"
	@echo "  make reset-db                 Borra DB, la levanta de 0, migra y siembra datos semilla"
	@echo "  make migrate                  Aplica las migraciones pendientes"
	@echo "  make migration m=\"mensaje\"    Genera una migración nueva con Alembic autogenerate"
	@echo "  make seed                     Crea los dos usuarios y clubes de prueba con sus 6 jugadores"
	@echo "  make db-shell                 Abre una terminal interactiva psql en el contenedor de Postgres"
	@echo "  make logs                     Muestra logs del contenedor Postgres en vivo"
	@echo ""
	@echo "Testing y Calidad:"
	@echo "  make test                     Corre todos los tests (acepta args=\"...\")"
	@echo "  make test-fast                Corre tests y frena en el primer fallo (-x)"
	@echo "  make test-lf                  Corre únicamente los tests que fallaron la última vez (--lf)"
	@echo "  make test-cov                 Corre tests con reporte de cobertura en consola"
	@echo "  make test-game                Corre exclusivamente los tests del motor de juego"
	@echo "  make test-api                 Corre exclusivamente los tests de endpoints y websockets"
	@echo "  make check                    Verificación completa de tests antes de commitear / abrir PR"
	@echo "  make clean                    Limpia caches (__pycache__, .pytest_cache) y SQLite de test"
	@echo "========================================================================"

# --- Dependencias y Setup ---

install:
	pip install -r requirements.txt

setup:
	@if [ ! -f .env ]; then \
		echo "Creando .env a partir de .env.example..."; \
		cp .env.example .env; \
		SECRET=$$(openssl rand -hex 32 2>/dev/null || echo "insecure_dev_secret_key_change_me"); \
		sed -i "s|<generala con: openssl rand -hex 32>|$$SECRET|" .env; \
	fi
	$(MAKE) up
	$(MAKE) migrate
	$(MAKE) seed
	@echo "Setup completado exitosamente."

# --- Base de datos y Docker ---

up:
	docker compose up -d --wait

down:
	docker compose down

down-v:
	docker compose down -v

reset-db: down-v up migrate seed
	@echo "Base de datos reiniciada desde cero y cargada con datos semilla."

migrate:
	alembic upgrade head

migration:
	@test -n "$(m)" || (echo 'Uso: make migration m="descripcion"'; exit 1)
	alembic revision --autogenerate -m "$(m)"

seed:
	@echo "Sembrando datos de desarrollo (usuarios, clubes y jugadores)..."
	$(PYTHON) -m scripts.create_user --email test@futbot.com --password test1234 --club "Test FC"
	$(PYTHON) -m scripts.create_user --email rival@futbot.com --password rival1234 --club "Rival FC"

db-shell:
	docker compose exec db psql -U futbot -d futbot

logs:
	docker compose logs -f db

# --- Ejecución de la API ---

run: up migrate
	uvicorn app.main:app --reload

# --- Tests ---

test:
	$(PYTEST) $(args)

test-fast:
	$(PYTEST) -x --tb=short $(args)

test-lf:
	$(PYTEST) --lf --tb=short $(args)

test-cov:
	$(PYTEST) --cov=app --cov-report=term-missing

test-game:
	$(PYTEST) tests/game/

test-api:
	$(PYTEST) tests/test_*.py

check: test
	@echo "Todos los tests pasaron exitosamente."

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -f tests/futbot_test.db
	rm -f .coverage
	@echo "Archivos temporales y cachés eliminados."
