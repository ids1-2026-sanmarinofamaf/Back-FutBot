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

### 4. Inicializar el entorno y la base de datos

```bash
make setup
```

Este comando automatiza la configuración inicial en un solo paso:
1. Crea el archivo `.env` a partir de `.env.example` y autogenera una `SECRET_KEY` segura (si `.env` no existía).
2. Levanta el contenedor de PostgreSQL en Docker (`make up`) y espera a que esté listo.
3. Aplica todas las migraciones con Alembic (`make migrate`).
4. Siembra los datos de desarrollo (`make seed`): crea las dos cuentas de prueba con sus respectivos clubes y sus 6 jugadores listos para jugar.

> **Nota:** Si preferís configurar el `.env` manualmente, podés hacer `cp .env.example .env` y generar tu clave con `openssl rand -hex 32`.

### 5. Arrancar la API

```bash
make run
```

Levanta el servidor Uvicorn con recarga automática en `http://127.0.0.1:8000`.

### 6. Verificar que funciona

- API: http://127.0.0.1:8000
- Documentación interactiva (Swagger): http://127.0.0.1:8000/docs

> Si aparece `ModuleNotFoundError: No module named 'app'`, verificá que el venv
> esté activado y que estés parado en la raíz del repo.

## Uso diario

Una vez hecha la puesta en marcha, el día a día es:

```bash
source .venv/bin/activate   # activar el entorno virtual
make run                    # asegura DB + migraciones + arranca la API
```

Para frenar: `Ctrl+C` corta la API y `make down` frena la base en Docker (los datos se conservan).

### Si necesitás reiniciar todo de cero

Si estuviste probando cambios o las migraciones quedaron en un estado inconsistente:

```bash
make reset-db
```

Borra la base por completo, la levanta de nuevo, corre las migraciones y vuelve a cargar los usuarios y jugadores de prueba.

### Después de cada `git pull`

```bash
make install   # por si alguien agregó dependencias
make run       # aplica las migraciones nuevas y levanta la API
```

## Comandos disponibles (Makefile)

| Comando | Qué hace |
|---|---|
| `make` / `make help` | Lista los comandos disponibles organizados por categoría |
| `make setup` | Puesta en marcha inicial (crea `.env`, levanta Postgres, migra y siembra datos) |
| `make install` | Instala las dependencias de Python |
| `make run` | Levanta la DB, aplica migraciones y corre la API con recarga automática |
| `make up` | Levanta Postgres en segundo plano y espera a que esté listo |
| `make down` | Frena Postgres (los datos se conservan) |
| `make down-v` | Frena Postgres y borra el volumen de datos |
| `make reset-db` | Reinicia la base desde cero (borra volumen, levanta, migra y corre `seed`) |
| `make seed` | Crea los dos usuarios de prueba con sus clubes y 6 jugadores cada uno |
| `make migrate` | Aplica las migraciones pendientes con Alembic |
| `make migration m="descripcion"` | Genera una migración nueva con autogenerate |
| `make db-shell` | Abre una consola interactiva `psql` dentro del contenedor |
| `make logs` | Sigue en vivo los logs del contenedor de base de datos |
| `make test` | Corre toda la suite de tests (acepta `args="..."`, ej: `make test args="-k match"`) |
| `make test-fast` | Corre tests deteniéndose en el primer fallo (`-x`) |
| `make test-lf` | Re-ejecuta únicamente los tests que fallaron en la última corrida (`--lf`) |
| `make test-cov` | Corre los tests y muestra el reporte de cobertura en consola |
| `make test-game` | Corre exclusivamente los tests del motor de juego (`tests/game/`) |
| `make test-api` | Corre exclusivamente los tests de endpoints y websockets |
| `make check` | Verificación de salud completa antes de commitear |
| `make clean` | Limpia caches (`__pycache__`, `.pytest_cache`) y base SQLite temporal |

## Datos de prueba y desarrollo (`make seed` / `make reset-db`)

Para probar la plataforma localmente y jugar partidos amistosos desde el frontend o Swagger, `make seed` (o `make reset-db`) genera automáticamente dos cuentas listas con sus respectivos clubes y los 6 jugadores necesarios (3 titulares y 3 suplentes, todos con PACSS = 60):

### Cuenta 1 (Local / Retador)
* **Email:** `test@futbot.com`
* **Contraseña:** `test1234`
* **Club:** `Test FC`
* **Jugadores (Power: 60, Agility: 60, Control: 60, Speed: 60, Strength: 60):**
  * Andy
  * Santiago
  * Santino
  * Lotu
  * Joaco
  * Luca

### Cuenta 2 (Visitante / Rival)
* **Email:** `rival@futbot.com`
* **Contraseña:** `rival1234`
* **Club:** `Rival FC`
* **Jugadores (Power: 60, Agility: 60, Control: 60, Speed: 60, Strength: 60):**
  * Santi
  * Julio
  * Lean
  * Chun
  * Gonzalo
  * Diego

Si durante el desarrollo modificás modelos o migraciones y querés volver a **probar todo de cero**, ejecutá:

```bash
make reset-db
```

Este comando frena Postgres, elimina su volumen para descartar datos viejos, lo vuelve a levantar con el esquema nuevo migrado y recarga las cuentas y jugadores iniciales.

## Tests

Los tests están en `tests/` y se pueden correr con distintas variantes:

```bash
make test             # Corre todos los tests
make test-fast        # Se detiene en el primer error (-x)
make test-lf          # Corre solo los últimos que fallaron (--lf)
make test-game        # Corre los tests de simulación física y motor
make test-api         # Corre los tests de endpoints y websockets
make test args="-k match -v"  # Permite pasar argumentos personalizados a pytest
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

### Comandos útiles para la base de datos

En lugar de recordar los comandos largos de Docker, podés usar los atajos del Makefile:

* `make reset-db` : Frena Postgres, **borra todos los datos**, levanta de nuevo, migra y siembra las cuentas/jugadores.
* `make down-v` : Frena Postgres y borra el volumen persistente de datos.
* `make logs` : Muestra los logs de Postgres en vivo.
* `make db-shell` : Abre una consola interactiva `psql` dentro del contenedor.

## Dependencias

Las dependencias están declaradas en `requirements.txt`.

Para agregar una nueva:

```bash
pip install nombre_paquete
pip freeze > requirements.txt
```

Commiteá el `requirements.txt` actualizado para que el resto del equipo la tenga
con `make install`.
