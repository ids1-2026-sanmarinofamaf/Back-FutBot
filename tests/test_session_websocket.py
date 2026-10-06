"""Tests del websocket /ws/sessions y del ConnectionManager que guarda las conexiones."""

# asyncio: para correr funciones async (como manager.broadcast) desde un test normal
import asyncio
# datetime/timedelta/timezone: para armar un token que ya esté vencido
from datetime import datetime, timedelta, timezone

# jwt: para firmar tokens "a mano" (vencidos o con otra clave)
import jwt
import pytest
# TestClient: cliente de prueba de FastAPI, sirve para HTTP y también para websockets
from fastapi.testclient import TestClient
# WebSocketDisconnect: la excepción que lanza el cliente cuando el servidor cierra/rechaza la conexión
from starlette.websockets import WebSocketDisconnect

from app.core.security import ALGORITHM, SECRET_KEY, create_access_token, get_password_hash
# ConnectionManager: la clase (para crear managers nuevos en los tests unitarios)
# manager: la instancia global que usa el endpoint de verdad
from app.core.ws_manager import ConnectionManager, manager
from app.database import SessionLocal
# Importamos la app REAL, no una app inventada como en el ejemplo de la documentación
from app.main import app
from app.models.club import Club
from app.models.user import User

# Email distinto al de test_auth.py para que los tests no se pisen entre sí
EMAIL = "ws@mail.com"
# Código de cierre que manda el servidor cuando rechaza el token (WS_1008_POLICY_VIOLATION)
POLICY_VIOLATION = 1008

# Un solo cliente para todo el archivo, igual que en test_auth.py
client = TestClient(app)


@pytest.fixture
def user():
    # Abrimos una sesión con la base de datos de test
    db = SessionLocal()
    # Creamos un usuario con su club (el modelo User necesita un club)
    user = User(email=EMAIL, hash_passwd=get_password_hash("secreta123"), club=Club(name="ws"))
    # Lo guardamos en la base
    db.add(user)
    db.commit()
    # refresh carga el id que le asignó la base de datos
    db.refresh(user)
    # yield: acá se corre el test; lo que sigue se ejecuta cuando el test termina
    yield user
    # Limpiamos todo para que el próximo test arranque con la base vacía
    db.query(Club).delete()
    db.query(User).delete()
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def clean_manager():
    # autouse=True: corre en TODOS los tests de este archivo sin tener que pedirlo
    # Vaciamos el manager global antes del test por si quedó algo de un test anterior
    manager.active.clear()
    yield
    # Y lo vaciamos después, para no ensuciar los tests de otros archivos
    manager.active.clear()


def ws_url(token):
    # El navegador no puede mandar headers en un websocket, por eso el token va en la URL
    return f"/ws/sessions?token={token}"


# ---------------------------------------------------------------------------
# Tests del endpoint /ws/sessions (usan el cliente, como si fuera el navegador)
# ---------------------------------------------------------------------------


def test_connect_with_valid_token_receives_welcome(user):
    # Generamos un token válido para el usuario creado por el fixture
    token = create_access_token(user.email)
    # websocket_connect abre la conexión; el "with" la cierra solo al salir del bloque
    with client.websocket_connect(ws_url(token)) as ws:
        # Lo primero que hace el endpoint al conectar es mandar el estado actual de los partidos amistosos
        assert ws.receive_json() == {"friendly_games": []}


def test_connected_user_is_registered_in_manager(user):
    token = create_access_token(user.email)
    with client.websocket_connect(ws_url(token)) as ws:
        # Leemos el estado inicial: así nos aseguramos de que manager.connect() ya se ejecutó
        ws.receive_json()
        # El manager guarda las conexiones por id de usuario
        assert user.id in manager.active
        # Con una sola pestaña abierta, el usuario tiene exactamente una conexión
        assert len(manager.active[user.id]) == 1


def test_disconnect_removes_user_from_manager(user):
    token = create_access_token(user.email)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.receive_json()
    # Al salir del "with" el cliente cierra la conexión: el servidor recibe
    # WebSocketDisconnect y el "finally" del endpoint llama a manager.disconnect()
    assert user.id not in manager.active


def test_client_messages_close_connection(user):
    token = create_access_token(user.email)
    with client.websocket_connect(ws_url(token)) as ws:
        ws.receive_json()
        # Si el cliente envía información, el endpoint cierra la conexión por violar el contrato server -> client
        ws.send_text("hola")

        with pytest.raises(WebSocketDisconnect) as exc:
            ws.receive_text()

        assert exc.value.code == POLICY_VIOLATION

    # Como la conexión fue cerrada, el usuario ya no debe estar registrado en el manager
    assert user.id not in manager.active


def test_same_user_with_two_tabs(user):
    token = create_access_token(user.email)
    # Abrimos la primera "pestaña"
    with client.websocket_connect(ws_url(token)) as tab1:
        tab1.receive_json()
        # Abrimos la segunda "pestaña" con el mismo usuario
        with client.websocket_connect(ws_url(token)) as tab2:
            tab2.receive_json()
            # El mismo usuario tiene dos conexiones guardadas
            assert len(manager.active[user.id]) == 2
        # Cerramos la segunda: el usuario sigue conectado por la primera
        assert len(manager.active[user.id]) == 1
    # Cerramos la primera: ya no le queda ninguna conexión y se borra del manager
    assert user.id not in manager.active


def test_invalid_token_is_rejected():
    # pytest.raises verifica que el bloque lance esa excepción
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(ws_url("esto-no-es-un-token")):
            pass
    # get_current_user_ws lanza WebSocketException con código 1008
    assert exc.value.code == POLICY_VIOLATION


def test_expired_token_is_rejected(user):
    # Armamos el token a mano con "exp" un minuto en el pasado
    payload = {
        "sub": EMAIL,
        "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        "jti": "x",
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(ws_url(token)):
            pass
    assert exc.value.code == POLICY_VIOLATION


def test_token_signed_with_other_key_is_rejected(user):
    # Token con datos correctos pero firmado con una clave que no es la del servidor
    payload = {
        "sub": EMAIL,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "jti": "x",
    }
    token = jwt.encode(payload, "otra-clave-otra-clave-otra-clave-1234", algorithm=ALGORITHM)
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(ws_url(token)):
            pass
    assert exc.value.code == POLICY_VIOLATION


def test_token_of_deleted_user_is_rejected():
    # El token está bien firmado, pero ese email no existe en la base
    # (no usamos el fixture user, así que la base está vacía)
    token = create_access_token("borrado@mail.com")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(ws_url(token)):
            pass
    assert exc.value.code == POLICY_VIOLATION


def test_missing_token_is_rejected():
    # Sin ?token= falla la validación del parámetro antes de llegar a nuestro código;
    # FastAPI también cierra esos websockets con 1008
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/sessions"):
            pass
    assert exc.value.code == POLICY_VIOLATION


def test_rejected_connection_is_not_registered():
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(ws_url("esto-no-es-un-token")):
            pass
    # Si el token es inválido nunca se llega a manager.connect()
    assert manager.active == {}


# ---------------------------------------------------------------------------
# Tests unitarios del ConnectionManager (sin cliente ni base de datos)
# ---------------------------------------------------------------------------


class FakeWebSocket:
    """Websocket falso: guarda lo que le mandan en vez de mandarlo por la red."""

    def __init__(self, broken=False):
        # broken=True simula una conexión caída (por ejemplo, el usuario cerró el navegador)
        self.broken = broken
        # Si se llamó a accept()
        self.accepted = False
        # Lista con todos los mensajes que "recibió" este websocket
        self.sent = []

    async def accept(self):
        self.accepted = True

    async def send_json(self, message):
        # Una conexión caída falla al intentar mandarle algo
        if self.broken:
            raise RuntimeError("conexion caida")
        self.sent.append(message)


def test_manager_connect_accepts_and_registers():
    # Manager nuevo: no tocamos el global que usa el endpoint
    m = ConnectionManager()
    ws = FakeWebSocket()
    # connect es async; asyncio.run lo ejecuta y espera a que termine
    asyncio.run(m.connect(1, ws))
    # Tiene que haber aceptado la conexión...
    assert ws.accepted
    # ...y guardarla bajo el usuario 1
    assert m.active == {1: {ws}}


def test_manager_disconnect_unknown_connection_does_not_fail():
    m = ConnectionManager()
    # Desconectar algo que nunca se conectó no debe lanzar error
    m.disconnect(99, FakeWebSocket())
    assert m.active == {}


def test_broadcast_reaches_every_connection():
    m = ConnectionManager()
    # Usuario 1 con dos pestañas, usuario 2 con una
    tab1, tab2, other = FakeWebSocket(), FakeWebSocket(), FakeWebSocket()
    asyncio.run(m.connect(1, tab1))
    asyncio.run(m.connect(1, tab2))
    asyncio.run(m.connect(2, other))
    asyncio.run(m.broadcast({"event": "arranca el partido"}))
    # Las tres conexiones recibieron el mensaje
    assert tab1.sent == [{"event": "arranca el partido"}]
    assert tab2.sent == [{"event": "arranca el partido"}]
    assert other.sent == [{"event": "arranca el partido"}]


def test_broadcast_removes_broken_connection_and_keeps_the_rest():
    m = ConnectionManager()
    ok = FakeWebSocket()
    broken = FakeWebSocket(broken=True)
    asyncio.run(m.connect(1, ok))
    asyncio.run(m.connect(2, broken))
    # Aunque una conexión falle, broadcast no debe lanzar la excepción
    asyncio.run(m.broadcast({"event": "hola"}))
    # La conexión sana recibió el mensaje
    assert ok.sent == [{"event": "hola"}]
    # La caída se sacó del manager (y como era la única del usuario 2, se borró el usuario)
    assert 2 not in m.active
    # El usuario 1 no se vio afectado
    assert 1 in m.active
