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

Para que `pytest` detecte los test automáticamente:

- Los archivos de test deben llamarse `test_*.py`.
- Las funciones del test deben comenzar con `test_`.

### Ejecutar todos los tests:

```bash
pytest
```

### Ejecutar un archivo de test especifico:

```bash
pytest tests/ruta/al/test_archivo.py
```

### Ejecutar un test específico:

```bash
pytest tests/ruta/al/test_archivo.py::test_nombre_del_test
```
