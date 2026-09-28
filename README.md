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

## Base de datos y migraciones (Alembic)

El esquema de la base se maneja **exclusivamente con Alembic**. No se usa `Base.metadata.create_all()`.

### Setup inicial

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e .                 # instala el proyecto en modo editable
alembic upgrade head             # crea/actualiza la base a la última versión
```

> `pip install -e .` permite que Alembic (y pytest) importen el paquete `app`.
> Si aparece `ModuleNotFoundError: No module named 'app'`, verificá que el venv
> esté activado y que corriste `alembic` desde la raíz del repo.

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

### Reglas del equipo

- Una migración por PR.
- Nunca editar una migración que ya está mergeada en `main`: si hay que corregir algo, se crea una nueva.
- Si al hacer rebase aparece el error de *multiple heads*, borrá tu migración,
  hacé `alembic upgrade head` y volvé a generarla encima de la última.
- Los datos iniciales (ej. comportamientos por defecto) se cargan como migración, no con scripts sueltos.

### Comandos útiles

| Comando | Qué hace |
|---|---|
| `alembic current` | Muestra en qué versión está tu base |
| `alembic history` | Lista todas las migraciones |
| `alembic downgrade -1` | Deshace la última migración |
| `alembic heads` | Muestra las "puntas" (debería haber una sola) |