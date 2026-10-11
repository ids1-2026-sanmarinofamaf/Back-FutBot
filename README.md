# FutBot Backend

Backend de FutBot desarrollado con FastAPI y SQLAlchemy.

## Requisitos

- Python 3.x
- [Docker](https://docs.docker.com/get-docker/) con el plugin `docker compose`
  (en Ubuntu: `sudo apt install docker-compose-v2`). Se usa para correr PostgreSQL,
  así que no hace falta instalar Postgres.
- `make` (en Ubuntu: `sudo apt install make`).

## Puesta en marcha (primera vez)

Seguí estos pasos en orden. Todos los comandos se corren desde la raíz del repo.

### 1. Clonar el repositorio

```bash
git clone git@github.com:ids1-2026-sanmarinofamaf/Back-FutBot.git
cd Back-FutBot
```

### 2. Crear y activar el entorno virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

El entorno virtual tiene que estar activado **cada vez** que trabajes en el proyecto
(vas a ver `(.venv)` al principio de la línea de la terminal).

### 3. Instalar las dependencias

```bash
make install
```

### 4. Crear el archivo `.env`

```bash
cp .env.example .env
```

Después abrí el `.env` y reemplazá el valor de `SECRET_KEY` por una clave generada con:

```bash
openssl rand -hex 32
```

El resto de los valores ya viene listo para desarrollo local: `DATABASE_URL` apunta al
Postgres de Docker. El `.env` se carga automáticamente con `python-dotenv` y está en
`.gitignore`, así que nunca se commitea.

### 5. Levantar el sistema

```bash
make run
```

Este comando hace tres cosas en orden:

1. Levanta PostgreSQL en Docker (`localhost:5432`) y espera a que esté listo.
2. Aplica las migraciones de Alembic (crea las tablas).
3. Arranca la API con recarga automática.

### 6. Verificar que funciona

- API: http://127.0.0.1:8000
- Documentación interactiva: http://127.0.0.1:8000/docs

> Si aparece `ModuleNotFoundError: No module named 'app'`, verificá que el venv
> esté activado y que estés parado en la raíz del repo.

## Uso diario

Una vez hecha la puesta en marcha, el día a día es:

```bash
source .venv/bin/activate   # activar el entorno virtual
make run                    # levantar DB + migraciones + API
```

Para frenar: `Ctrl+C` corta la API y `make down` frena la base. Los datos se conservan.

### Después de cada `git pull`

```bash
make install   # por si alguien agregó dependencias
make run       # aplica las migraciones nuevas y levanta la API
```

## Comandos disponibles (Makefile)

| Comando | Qué hace |
|---|---|
| `make` / `make help` | Lista los comandos disponibles |
| `make install` | Instala las dependencias de Python |
| `make up` | Levanta Postgres y espera a que esté listo |
| `make down` | Frena Postgres (los datos se conservan) |
| `make migrate` | Aplica las migraciones pendientes |
| `make migration m="descripcion"` | Genera una migración nueva con autogenerate |
| `make run` | Levanta la DB, aplica migraciones y corre la API |
| `make test` | Corre los tests |

## Tests

Los tests están en `tests/` y se corren con:

```bash
make test
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

Credenciales de la base local: usuario `futbot`, contraseña `futbot`, base `futbot`.
Son solo para desarrollo.

### Crear una migración (cuando cambiás un modelo)

1. Modificá el modelo en `app/models/`.
2. Generá la migración:
   ```bash
   make migration m="descripcion corta del cambio"
   ```
3. **Revisá el archivo generado** en `alembic/versions/` antes de commitear.
   El autogenerate no detecta todo (renombres de columnas, algunos cambios de enums).
4. Aplicala localmente: `make migrate`.
5. Commiteá la migración **en el mismo PR** que el cambio del modelo.

### Comandos útiles de Docker

* `docker compose down -v` : Frena la base **y borra todos los datos** (base limpia)
* `docker compose logs -f db` : Muestra los logs de Postgres
* `docker exec -it futbot-db psql -U futbot` : Abre una consola SQL

## Dependencias

Las dependencias están declaradas en `requirements.txt`.

Para agregar una nueva:

```bash
pip install nombre_paquete
pip freeze > requirements.txt
```

Commiteá el `requirements.txt` actualizado para que el resto del equipo la tenga
con `make install`.
