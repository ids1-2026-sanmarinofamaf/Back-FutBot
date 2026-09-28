# app/database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "Falta la variable de entorno DATABASE_URL (ej: sqlite:///./futbot.db)"
    )

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {} # check_same_thread tiene que aplicarse solo con SQLite, porque MySQL no lo acepta:

# Motor: fuente central de conexiones a la base de datos.
engine = create_engine(DATABASE_URL, echo=True, connect_args=connect_args)

# Fábrica de sesiones: cada request va a pedir una instancia nueva
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    """Clase base de la que heredan todos los modelos ORM (app/models)."""
    pass

def get_db():
    """Dependency de FastAPI: abre una sesión por request y la cierra al final."""
    db = SessionLocal() 
    try:
        yield db
    finally:
        db.close() # se ejecuta siempre, aunque el endpoint tire un error

