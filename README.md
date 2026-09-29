# FutBot Backend

Backend de FutBot desarrollado con FastAPI y SQLAlchemy.

## Requisitos

- Python 3.x

## Instalación

### Crear el entorno virtual:

```bash
python3 -m venv .venv
```

### Activar el entorno virtual

```bash
source .venv/bin/activate
```

### Instalar dependencias

```bash
pip install -r requirements.txt
```

## Ejecutar

Con el entorno virtual activado:

```bash
uvicorn app.main:app --reload
```

Por defecto, el backend estará disponible en: 

http://127.0.0.1:8000

La documentación interactiva de FastAPI estará disponible en:

http://127.0.0.1:8000/docs

## Dependencias

Las dependencias se encuentra declaradas en: 

requirements.txt

Agregar una nueva dependencia:

```bash
pip install nombre_paquete
```

Actualizar requirements.txt

```bash
pip freeze > requirements.txt
```

## Tests

Los tests del backend se encuentran en:

tests/

Se corren con:

```bash
pytest
```

Los tests **no usan la base de desarrollo**: `tests/conftest.py` apunta `DATABASE_URL` a una
base SQLite propia (`tests/futbot_test.db`), le aplica las migraciones al empezar y la borra al
terminar. No hace falta tener el contenedor de Postgres levantado.

Para correrlos contra otra base (por ejemplo, un Postgres de test), definí `TEST_DATABASE_URL`:

```bash
TEST_DATABASE_URL=postgresql+psycopg://futbot:futbot@localhost:5432/futbot_test pytest
```

## Base de datos y migraciones (Alembic)

El esquema de la base se maneja **exclusivamente con Alembic**. No se usa `Base.metadata.create_all()`.

La base es PostgreSQL y corre en un contenedor Docker, así que no hace falta instalar Postgres.

### Requisitos

- [Docker](https://docs.docker.com/get-docker/) con el plugin `docker compose`
  (en Ubuntu: `sudo apt install docker-compose-v2`).
- Haber seguido los pasos de [Instalación](#instalación): entorno virtual creado y
  activado, y dependencias instaladas.

### Setup inicial

Todos los comandos se corren desde la raíz del repo y con el entorno virtual activado.

#### 1. Crear el archivo `.env`

```bash
cp .env.example .env
```

El `.env` ya viene apuntando al Postgres de Docker. Se carga automáticamente
con `python-dotenv`, así que no hace falta exportar ninguna variable.

#### 2. Levantar la base de datos

```bash
docker compose up -d
```

Levanta PostgreSQL en `localhost:5432` (usuario `futbot`, contraseña `futbot`, base `futbot`).
Estas credenciales son solo para desarrollo local.

#### 3. Aplicar las migraciones

```bash
alembic upgrade head
```

Crea las tablas o las actualiza a la última versión.

Con esto ya se puede [ejecutar el backend](#ejecutar).

> Si aparece `ModuleNotFoundError: No module named 'app'`, verificá que el venv
> esté activado y que corriste `alembic` desde la raíz del repo.

### Comandos de Docker

* `docker compose up -d` : Levanta la base (en segundo plano)
* `docker compose down` : La frena. Los datos se conservan 
* `docker compose down -v` : La frena **y borra todos los datos** (base limpia)
* `docker compose logs -f db` :  Muestra los logs de Postgres
* `docker exec -it futbot-db psql -U futbot` : Abre una consola SQL

### Después de cada `git pull`

```bash
alembic upgrade head
```

Si alguien agregó una migración, esto actualiza tu base local sin perder datos.

### Crear una migración (cuando cambiás un modelo)

1. Modificá el modelo en `app/models/`.
2. Generá la migración:
```bash
   alembic revision --autogenerate -m "descripcion corta del cambio"
```
3. **Revisá el archivo generado** en `alembic/versions/` antes de commitear.
   El autogenerate no detecta todo (renombres de columnas, algunos cambios de enums).
4. Aplicala localmente: `alembic upgrade head`.
5. Commiteá la migración **en el mismo PR** que el cambio del modelo.
