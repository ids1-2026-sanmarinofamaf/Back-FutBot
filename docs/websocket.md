# WebSocket de sesiones (`ws/sessions`)

Este documento explica cómo funciona la conexión WebSocket que el frontend abre después de iniciar
sesión: qué hace cada clase y función, en qué archivo vive y cómo se conectan entre sí. Cubre el
ticket **SCRUM-49** (conexión websocket de sesiones).

Se apoya en la autenticación con JWT ya implementada; ver [auth.md](auth.md).

---

## 1. Qué pide el ticket

| Requisito | Detalle |
|---|---|
| Endpoint | WebSocket en `ws/sessions`. |
| Para qué sirve | Que el servidor le avise al usuario sobre ligas y partidos amistosos disponibles o en juego. |
| Autenticación | El cliente se conecta con el query param `token`, que tiene el JWT que devolvió `POST /sessions`. |
| Al conectar | El servidor envía el mensaje `"Bienvenido"`. |
| Usuario real | Solo se aceptan conexiones cuyo token corresponde a un usuario que existe en la base. Las demás se rechazan. |
| Independencia | La conexión de un usuario no se ve afectada por lo que pase con las de otros usuarios. |
| Desconexión | Si un usuario cierra su conexión, el backend deja de enviarle actualizaciones. |

Contrato:

| Endpoint | Request | Respuestas |
|---|---|---|
| `ws://<host>/ws/sessions?token=<jwt>` | Handshake WebSocket con el token en la URL | Conexión aceptada y mensaje `"Bienvenido"` · Conexión rechazada con código `1008` si el token falta, es inválido, está vencido o el usuario no existe |

---

## 2. WebSocket en dos minutos (teoría)

Con **HTTP**, el cliente pregunta y el servidor responde; para enterarse de algo nuevo el cliente
tendría que volver a preguntar cada tanto (*polling*, que el enunciado prohíbe).

Con **WebSocket**, el cliente abre **una conexión que queda abierta**, y por ella cualquiera de los
dos lados puede mandar mensajes en cualquier momento. Así el servidor puede avisar de un cambio
apenas ocurre.

Ciclo de vida de una conexión:

1. **Handshake**: el cliente hace un request HTTP especial pidiendo "pasar a WebSocket".
2. **Accept**: el servidor acepta (`websocket.accept()`). Desde acá la conexión está abierta.
3. **Mensajes**: los dos lados envían y reciben (`send_text` / `receive_text`).
4. **Close**: alguno de los dos cierra la conexión, con un **código de cierre**.

Códigos de cierre que aparecen acá:

| Código | Significado | Cuándo lo vemos |
|---|---|---|
| `1000` | Cierre normal | El cliente cierra la pestaña o llama a `ws.close()`. |
| `1008` | Violación de política | El servidor rechaza la conexión porque el token no es válido. |

### Por qué el token va en la URL y no en un header

En HTTP mandamos el token en el header `Authorization: Bearer <token>`. Pero el navegador **no
permite** agregar headers al abrir un WebSocket (`new WebSocket(url)` no tiene esa opción). Por eso
el ticket pide mandarlo como query param: `?token=<jwt>`.

---

## 3. Mapa de módulos

Cada capa importa solo de las capas **de abajo**. Lo nuevo de este ticket está marcado con ★; el
resto ya existía para el login.

```
                ┌─────────────────────────────┐
                │         app/main.py         │  registra el router ★
                └──────────────┬──────────────┘
                               │ include_router
                               ▼
                ┌─────────────────────────────┐
                │ app/api/sessions_websocket  │ ★  ROUTER (WebSocket)
                │ websocket_endpoint          │    /ws/sessions
                └───────┬─────────────┬───────┘
     Depends(get_current_user_ws)     │ connect / disconnect
                        │             ▼
                        │   ┌──────────────────────────┐
                        │   │ app/core/ws_manager.py   │ ★  REGISTRO DE CONEXIONES
                        │   │ ConnectionManager        │    (en memoria, sin base)
                        │   │ manager (instancia única)│
                        │   └──────────────────────────┘
                        ▼
                ┌─────────────────────────────┐
                │      app/api/deps.py        │ ★  DEPENDENCIAS
                │      get_current_user_ws    │
                └──────────────┬──────────────┘
                               ▼
                ┌─────────────────────────────┐
                │ app/services/auth_service.py│    LÓGICA DE NEGOCIO (ya existía)
                │ get_user_from_token         │
                └───────┬─────────────┬───────┘
                        ▼             ▼
          app/core/security.py   app/repositories/user_repository.py
          decode_access_token    get_by_email
```

| Capa | Archivo | Qué contiene |
|---|---|---|
| Router | `app/api/sessions_websocket.py` | `router`, `websocket_endpoint` (`/ws/sessions`) |
| Registro de conexiones | `app/core/ws_manager.py` | `ConnectionManager`, `manager` |
| Dependencias | `app/api/deps.py` | `get_current_user_ws` |
| Servicio | `app/services/auth_service.py` | `get_user_from_token`, `InvalidToken` (sin cambios) |
| Cripto | `app/core/security.py` | `decode_access_token` (sin cambios) |
| Repositorio | `app/repositories/user_repository.py` | `get_by_email` (sin cambios) |
| App | `app/main.py` | `app.include_router(sessions_websocket.router)` |

**Idea clave:** la validación del token **no se repitió**. HTTP (`get_current_user`) y WebSocket
(`get_current_user_ws`) usan la misma función `auth_service.get_user_from_token`. Lo único que
cambia entre los dos es *de dónde* se lee el token y *qué error* se devuelve.

---

## 4. Qué hace cada clase y función

### 4.1 `app/core/ws_manager.py` — registro de conexiones

Guarda en memoria qué conexiones están abiertas y permite mandarles mensajes a todas. No sabe nada
de tokens ni de la base: solo recibe un `user_id` y un `WebSocket`.

#### `class ConnectionManager`

##### `__init__(self)`

Crea el atributo `self.active`:

```python
self.active: dict[int, set[WebSocket]] = {}
```

- La **clave** es el `id` del usuario (`User.id`).
- El **valor** es un `set` con todas las conexiones abiertas de ese usuario. Es un conjunto y no una
  sola conexión porque un usuario puede tener **varias pestañas** abiertas.

Ejemplo de cómo se ve con dos usuarios conectados:

```python
{
    7:  {ws_pestaña1, ws_pestaña2},
    12: {ws_a},
}
```

Se eligió `set` porque no admite repetidos y tiene `discard`, que saca un elemento sin fallar si no
está.

##### `async connect(self, user_id, websocket)`

```python
await websocket.accept()
self.active.setdefault(user_id, set()).add(websocket)
```

1. `accept()` completa el handshake: desde acá la conexión está abierta.
2. `setdefault(user_id, set())` devuelve el set del usuario; si todavía no tenía uno, lo crea
   vacío. Después `.add(websocket)` agrega la conexión nueva.

Es `async` porque `accept()` es una operación de red y hay que esperarla con `await`.

##### `disconnect(self, user_id, websocket)`

```python
connections = self.active.get(user_id)
if connections is None:
    return
connections.discard(websocket)
if not connections:
    del self.active[user_id]
```

1. `.get()` devuelve `None` si el usuario no está (en vez de lanzar `KeyError`). En ese caso no hay
   nada que sacar.
2. `discard` saca la conexión, y **no falla si ya no estaba**. Esto importa porque una misma
   conexión puede intentar sacarse dos veces: una desde `broadcast` (al fallar un envío) y otra
   desde el endpoint (al recibir `WebSocketDisconnect`).
3. Si al usuario no le quedan conexiones, se borra su clave para no acumular sets vacíos.

No es `async` porque solo modifica el diccionario, no hace nada de red.

Esta función cumple el criterio "si un usuario cierra su conexión, el backend deja de enviarle
actualizaciones": una vez fuera de `self.active`, `broadcast` ya no la ve.

##### `async broadcast(self, message)`

```python
targets = [
    (user_id, conn)
    for user_id, connections in self.active.items()
    for conn in connections
]
for user_id, conn in targets:
    try:
        await conn.send_text(message)
    except Exception:
        self.disconnect(user_id, conn)
```

Manda `message` a **todas** las conexiones abiertas.

1. **Primero arma una copia** (`targets`), una lista plana de pares `(usuario, conexión)`. Cada
   `await send_text(...)` pausa esta función y deja correr otras tareas; si en ese momento alguien se
   conecta o desconecta, `self.active` cambia. Recorrer el diccionario original lanzaría
   `RuntimeError: dictionary changed size during iteration`. La copia no cambia.
2. **Después envía conexión por conexión.** Si un envío falla (por ejemplo, el cliente se cayó sin
   avisar), se atrapa el error y se saca **solo esa** conexión. El resto sigue recibiendo.

Esto cumple el criterio "los usuarios mantienen su conexión indistintamente de los cambios en las
conexiones de otros usuarios".

#### `manager = ConnectionManager()`

La **única instancia** del gestor, creada al importar el módulo. Todo el que necesite las conexiones
tiene que importar este mismo objeto:

```python
from app.core.ws_manager import manager
```

Si cada módulo creara su propio `ConnectionManager()`, cada uno tendría su propio diccionario
vacío y no vería las conexiones de los demás.

> **Ojo:** el registro vive en la memoria del proceso. Si el servidor se reinicia, se pierden todas
> las conexiones (los clientes tienen que reconectarse). Y si algún día se corre con varios workers
> de uvicorn, cada worker tendría su propio `manager`.

---

### 4.2 `app/api/deps.py` — `get_current_user_ws`

```python
def get_current_user_ws(
    token: Annotated[str, Query()],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    try:
        return auth_service.get_user_from_token(db, token)
    except auth_service.InvalidToken:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
```

Es la versión WebSocket de `get_current_user`. Recibe el token, devuelve el `User` o rechaza la
conexión.

**Parámetros**

| Parámetro | De dónde sale | Para qué |
|---|---|---|
| `token: Annotated[str, Query()]` | Query param `?token=...` de la URL | El JWT. `Query()` le dice a FastAPI que lo lea de la URL; el nombre del parámetro (`token`) tiene que coincidir con el de la URL. Es `str` sin valor por defecto, así que es **obligatorio**: si falta, FastAPI rechaza la conexión solo, también con `1008`. |
| `db: Annotated[Session, Depends(get_db)]` | `app/database.py` | Sesión de la base, que `get_user_from_token` necesita para buscar al usuario. |

**Qué hace**

1. Llama a `auth_service.get_user_from_token(db, token)`, que decodifica el JWT (firma, vencimiento,
   claims) y busca al usuario por el email del payload.
2. Si todo está bien, devuelve el `User`.
3. Si `get_user_from_token` lanza `InvalidToken` (token roto, vencido, firmado con otra clave o de un
   usuario que no existe), lanza `WebSocketException(1008)`.

**Diferencias con `get_current_user` (HTTP)**

| | `get_current_user` (HTTP) | `get_current_user_ws` (WebSocket) |
|---|---|---|
| Lee el token de | Header `Authorization: Bearer` (`bearer_scheme`) | Query param `?token=` (`Query()`) |
| Error | `HTTPException(401)` | `WebSocketException(1008)` |
| Validación | `auth_service.get_user_from_token` | `auth_service.get_user_from_token` (la misma) |

Como la dependencia corre **antes** del `accept()`, un token inválido hace que la conexión se
rechace en el handshake: nunca llega a abrirse.

---

### 4.3 `app/api/sessions_websocket.py` — el endpoint

#### `router = APIRouter(tags=["sessions"])`

El router de este módulo. `main.py` lo registra con `include_router`.

#### `async websocket_endpoint(websocket, user)`

```python
@router.websocket("/ws/sessions")
async def websocket_endpoint(
    websocket: WebSocket,
    user: Annotated[User, Depends(get_current_user_ws)],
):
    await manager.connect(user.id, websocket)
    try:
        await websocket.send_text("Bienvenido")
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(user.id, websocket)
```

**Parámetros**

| Parámetro | Qué es |
|---|---|
| `websocket: WebSocket` | La conexión. FastAPI la crea y la pasa sola. |
| `user: Annotated[User, Depends(get_current_user_ws)]` | El usuario autenticado. Cuando el código del endpoint empieza a correr, el token **ya fue validado**; si no era válido, la función nunca se ejecuta. |

**Qué hace, paso a paso**

1. `manager.connect(user.id, websocket)` acepta la conexión y la registra bajo el id del usuario.
   Está **antes** del `try`: si ni siquiera se pudo aceptar, no hay nada que desconectar.
2. `send_text("Bienvenido")` cumple el requisito del mensaje inicial.
3. `while True: receive_text()` mantiene viva la conexión. El cliente no manda nada útil por este
   canal; el loop sirve para **enterarse de cuándo se desconecta**: en ese momento `receive_text()`
   lanza `WebSocketDisconnect`.
4. `except WebSocketDisconnect: pass` toma la desconexión normal como algo esperado, no como error.
5. `finally: manager.disconnect(...)` se ejecuta **siempre**, salga como salga la función
   (desconexión normal o cualquier otro error). Así nunca queda registrada una conexión cerrada.

---

### 4.4 `app/main.py`

```python
from app.api import auth, users, sessions_websocket
...
app.include_router(sessions_websocket.router)
```

Registra el router del WebSocket en la app. Sin esto la ruta `/ws/sessions` no existe.

> Los WebSockets **no pasan por el `CORSMiddleware`**. Si en algún momento se quiere restringir
> desde qué origen se conectan, hay que revisar a mano el header `Origin` del handshake.

---

### 4.5 Funciones que ya existían y se reutilizan

Están explicadas en detalle en [auth.md](auth.md#4-qué-hace-cada-función):

| Función | Archivo | Qué aporta acá |
|---|---|---|
| `get_user_from_token(db, token)` | `services/auth_service.py` | Valida el JWT y devuelve el `User`, o lanza `InvalidToken`. |
| `decode_access_token(token)` | `core/security.py` | Verifica firma, `exp`, y que estén `sub`, `exp` y `jti`. |
| `get_by_email(db, email)` | `repositories/user_repository.py` | Confirma que el usuario existe en la base. |
| `get_db()` | `database.py` | Abre la sesión de la base. |

---

## 5. Recorrido de una conexión

### Conexión aceptada

```
Frontend                 FastAPI         deps.get_current_user_ws   auth_service        ws_manager.manager
   │ POST /sessions → token (ver auth.md)     │                         │                      │
   │                        │                 │                         │                      │
   │ ws://.../ws/sessions   │                 │                         │                      │
   │   ?token=<jwt>         │                 │                         │                      │
   │───────────────────────▶│ lee ?token= ───▶│                         │                      │
   │                        │                 │ get_user_from_token ───▶│ decode + get_by_email│
   │                        │                 │◀────────────── User ────│                      │
   │                        │◀───── user ─────│                         │                      │
   │                        │ websocket_endpoint(websocket, user)        │                      │
   │                        │ connect(user.id, websocket) ──────────────────────────────────────▶│ accept()
   │◀═══ conexión abierta ══│                                                                   │ active[id].add(ws)
   │◀══ "Bienvenido" ═══════│                                                                   │
   │                        │ while True: receive_text()  (esperando)                           │
```

### Conexión rechazada

```
Frontend                 FastAPI         deps.get_current_user_ws   auth_service
   │ ws://.../ws/sessions   │                 │                         │
   │   ?token=<malo>        │                 │                         │
   │───────────────────────▶│ lee ?token= ───▶│ get_user_from_token ───▶│
   │                        │                 │◀──────── InvalidToken ──│
   │                        │                 │ raise WebSocketException(1008)
   │◀══ cierre 1008 ════════│   (websocket_endpoint nunca se ejecuta; nada queda registrado)
```

### El usuario se desconecta

```
Frontend                websocket_endpoint                   ws_manager.manager
   │ cierra la pestaña /       │                                    │
   │ ws.close()                │                                    │
   │══ close ═════════════════▶│ receive_text() lanza               │
   │                           │ WebSocketDisconnect                │
   │                           │ finally: disconnect(user.id, ws) ─▶│ active[id].discard(ws)
   │                           │                                    │ (si queda vacío, borra la clave)
```

### Un broadcast

```
quien llame                    ws_manager.manager                   conexiones
   │ await manager.broadcast(msg) ─▶│ copia de active → targets       │
   │                                │ send_text(msg) ────────────────▶│ usuario 7, pestaña 1 ✔
   │                                │ send_text(msg) ────────────────▶│ usuario 7, pestaña 2 ✔
   │                                │ send_text(msg) ────────────────▶│ usuario 12 ✘ (se cayó)
   │                                │ disconnect(12, ws)              │
   │                                │ (los demás ya recibieron; el 12 deja de estar registrado)
```

### Qué pasa en cada caso

| Situación | Dónde se detecta | Resultado |
|---|---|---|
| Token válido de un usuario existente | `get_current_user_ws` | Conexión aceptada + `"Bienvenido"` |
| Falta `?token=` | FastAPI (parámetro obligatorio) | Cierre `1008` |
| Token mal formado | `decode_access_token` → `InvalidToken` | Cierre `1008` |
| Token firmado con otra clave o modificado | `decode_access_token` → `InvalidToken` | Cierre `1008` |
| Token vencido | `decode_access_token` → `InvalidToken` | Cierre `1008` |
| Token válido de un usuario que no existe | `get_user_from_token` → `InvalidToken` | Cierre `1008` |
| El usuario abre otra pestaña | `ConnectionManager.connect` | Se agrega al set del mismo usuario |
| El usuario cierra una pestaña | `websocket_endpoint` → `disconnect` | Se saca solo esa conexión |
| Una conexión se cae sin avisar | `broadcast` (falla `send_text`) | Se saca esa conexión; los demás reciben igual |

---

## 6. Fuera de este ticket: notificar ligas y partidos amistosos

Notificar el estado y la disponibilidad de ligas y partidos amistosos a todos los usuarios conectados
**no es parte de SCRUM-49**: se quitó de sus criterios de aceptación y se implementa en otro ticket,
junto con los modelos, repositorios y services de `league` y `friendly_game` (hoy vacíos).

Lo que este ticket deja listo es el mecanismo: `manager.broadcast(...)`. Cuando se implementen esos
dominios, cada vez que se cree, se una alguien, se cancele o empiece una liga o un amistoso, el
service correspondiente tiene que:

1. Leer de la base las ligas y amistosos disponibles o en juego.
2. Llamar a `await manager.broadcast(...)` con esos datos.

Hay dos cosas a definir en ese ticket:

- **Formato del mensaje.** No está definido ni en el ticket ni en [API.md](API.md): si se manda la
  lista completa o solo lo que cambió, y con qué forma de JSON. Hay que acordarlo con el frontend.
- **Sync vs. async.** Los services actuales son funciones normales (`def`) y `broadcast` es `async`.
  Para llamarlo hay que hacer `async` esos endpoints, usar `BackgroundTasks` de FastAPI, o
  `anyio.from_thread.run(manager.broadcast, msg)` desde código sync.

---

## 7. Dependencias

Para que uvicorn acepte conexiones WebSocket hace falta la librería `websockets` en
`requirements.txt`. Sin ella, uvicorn responde a los handshakes con un error.

---

## 8. Cómo probarlo a mano

1. Levantar el backend (`uvicorn app.main:app --reload`).
2. Hacer login con `POST /sessions` (desde `/docs` o el frontend) y copiar el `token`.
3. En la consola del navegador:

```js
const ws = new WebSocket("ws://localhost:8000/ws/sessions?token=PEGAR_EL_TOKEN");
ws.onmessage = (e) => console.log("mensaje:", e.data);      // → "Bienvenido"
ws.onclose   = (e) => console.log("cerrado, código", e.code); // token inválido → 1008
```

4. Para cerrar desde el cliente: `ws.close()`.

También se puede probar con Postman (tiene cliente WebSocket) o con `websocat`:

```bash
websocat "ws://localhost:8000/ws/sessions?token=PEGAR_EL_TOKEN"
```

En tests con pytest se usa `TestClient(app).websocket_connect("/ws/sessions?token=...")`; si la
conexión se rechaza, lanza `WebSocketDisconnect` con `code == 1008`.
