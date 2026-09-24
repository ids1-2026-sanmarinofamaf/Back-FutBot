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