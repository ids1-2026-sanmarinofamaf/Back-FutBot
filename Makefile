.PHONY: help install up down migrate migration run test

help:
	@echo "Comandos disponibles:"
	@echo "  make install                  Instala las dependencias de Python"
	@echo "  make up                       Levanta Postgres y espera a que esté listo"
	@echo "  make down                     Frena Postgres (los datos se conservan)"
	@echo "  make migrate                  Aplica las migraciones pendientes"
	@echo "  make migration m=\"mensaje\"    Genera una migración nueva"
	@echo "  make run                      Levanta la DB, migra y corre la API"
	@echo "  make test                     Corre los tests"

install:
	pip install -r requirements.txt

up:
	docker compose up -d --wait

down:
	docker compose down

migrate:
	alembic upgrade head

migration:
	@test -n "$(m)" || (echo 'Uso: make migration m="descripcion"'; exit 1)
	alembic revision --autogenerate -m "$(m)"

run: up migrate
	uvicorn app.main:app --reload

test:
	pytest
