# Fixture y tabla de posiciones al iniciar una liga

Este documento explica qué se hizo en la rama del ticket **SCRUM-146** (generación de la tabla de
posiciones y sorteo del fixture al iniciar una liga): qué modelos se agregaron, cómo fluye el inicio
de una liga, cómo se avisa por WebSocket y qué cubren los tests.

Se apoya en el endpoint de inicio de liga de **SCRUM-141** (`PATCH /leagues/{league_id}`) y en el
WebSocket de liga de **SCRUM-163** (`ws/league/{league_id}`).

> **Para el front:** todo lo que necesitás está en la [sección 11](#11-integración-con-el-front).
> Los payloads completos de ejemplo están en la 11.6 y cómo mostrar las fechas en la 11.7.

### Últimos cambios

| Cambio | Impacto en el front |
|---|---|
| El fixture se organiza en **fechas** (método del círculo). Ningún club juega dos veces en la misma fecha y, con cantidad impar de clubes, cada club queda libre una fecha. | El orden de los partidos ahora va fecha por fecha. |
| Cada partido trae el campo nuevo **`round`** (número de fecha, empieza en 1), guardado en `Match.round`. | Se puede agrupar y pintar el fixture por fecha usando `round`. |
| Nueva migración que agrega la columna `round` a `matches`. | Ninguno. En el back hay que correr `alembic upgrade head`. |
| Se sacó un `db.flush()` que sobraba en `start_league`. | Ninguno. |

---

## 1. Qué pide el ticket

| Requisito | Detalle |
|---|---|
| Cuándo | Al pasar la liga de `POR_COMENZAR` a `INICIADA`, en la misma operación del `PATCH`. |
| Fixture | Todos contra todos a una sola rueda: con n clubes, n·(n−1)/2 partidos, cada par una sola vez. |
| Partidos | Cada partido es un `Match` en `POR_COMENZAR` con dos `MatchParticipation` (`LOCAL` y `VISITANTE`). |
| Sorteo | Se sortean el orden de los partidos y la localía. Acepta una semilla opcional para los tests. |
| Fechas | Los partidos se organizan en fechas: ningún club juega dos veces en la misma fecha y, con n impar, cada club queda libre una vez. |
| Plantilla | Cada participación usa el roster que el club armó para esa liga, no otro. |
| Tabla | Una fila por club con puntos, PJ, PG, PE, PP, GF, GC y DG en 0. |
| Transacción | Estado, fixture y tabla se guardan juntos. Si algo falla, la liga queda en `POR_COMENZAR` sin partidos. |
| Aviso | Después de guardar se emite `league_started` al canal de la liga, con fixture y tabla. |
| Consulta | `GET /leagues/{league_id}` devuelve fixture y tabla cuando la liga está `INICIADA`. |

---

## 2. Qué se agregó en la rama

| Área | Archivo | Qué hay |
|---|---|---|
| Modelos | [app/models/match.py](../app/models/match.py) | `Match` y el enum `MatchState`. |
| Modelos | [app/models/match_participation.py](../app/models/match_participation.py) | `MatchParticipation` y el enum `MatchRole`. |
| Modelos | [app/models/league.py](../app/models/league.py) | Relación `League.matches`, ordenada por `match_order`. |
| Migración | [alembic/versions/fe788b9cf5b5_crear_tablas_de_partidos.py](../alembic/versions/fe788b9cf5b5_crear_tablas_de_partidos.py) | Tablas `matches` y `match_participations`. |
| Schemas | [app/schemas/league.py](../app/schemas/league.py) | `FixtureClub`, `FixtureMatchItem`, `StandingRow`, `LeagueStartedEvent`, `LeagueDetail`. |
| Sorteo | [app/services/fixture_service.py](../app/services/fixture_service.py) | `generate_fixture(club_ids, seed)`: fechas con el método del círculo. |
| Service | [app/services/league_service.py](../app/services/league_service.py) | Creación de partidos en `start_league`, `build_league_state` y `get_league_detail`. |
| Endpoint | [app/api/leagues.py](../app/api/leagues.py) | Emisión de `league_started` en el `PATCH` y nuevo `GET /leagues/{league_id}`. |
| WebSocket | [app/services/league_websocket_service.py](../app/services/league_websocket_service.py) | `broadcast` acepta `LeagueStartedEvent`. |
| Tests | `tests/test_fixture_service.py`, `tests/test_start_league_integration.py`, `tests/test_get_league_api.py`, `tests/test_league_started_broadcast.py` | Ver sección 9. |

---

## 3. Modelos

```
League ──< Match ──< MatchParticipation >── Club
   │                        │
   └──< LeagueParticipation ┘── Roster (el de la liga)
```

### `Match`

| Campo | Tipo | Para qué |
|---|---|---|
| `id` | int | Lo asigna el service con `match_repository.get_next_match_id(db)` (secuencia `match_id_seq`), la misma que usan los amistosos, para que los ids no choquen. |
| `league_id` | int \| null | Liga a la que pertenece. Es nullable para que más adelante un amistoso también pueda tener su `Match`. |
| `state` | `MatchState` | `POR_COMENZAR`, `JUGANDO`, `FINALIZADO`. |
| `match_order` | int \| null | Posición del partido en el fixture sorteado (empieza en 1). Sigue el orden de las fechas: primero todos los partidos de la fecha 1, después los de la 2, etc. |
| `round` | int \| null | Fecha del fixture a la que pertenece el partido (empieza en 1). Es nullable porque un amistoso no tiene fecha. |

### `MatchParticipation`

| Campo | Tipo | Para qué |
|---|---|---|
| `match_id` | int | Partido. |
| `club_id` | int | Club que juega. |
| `roster_id` | int | El roster de la `LeagueParticipation` del club, o sea la plantilla de esa liga. |
| `role` | `MatchRole` | `LOCAL` o `VISITANTE`. |

Restricciones en la base: `UniqueConstraint(match_id, role)`, que permite un solo local y un solo
visitante por partido, y `UniqueConstraint(match_id, club_id)`, que impide que un club juegue contra
sí mismo.

### La tabla de posiciones no es un modelo nuevo

La tabla son las filas de `LeagueParticipation` de la liga, que ya tenían `points`,
`matches_played`, `matches_won`, `matches_drawn`, `matches_lost`, `goals_for` y `goals_against` con
valor por defecto 0. La diferencia de gol no se guarda: se calcula como
`goals_for - goals_against` al armar el schema.

### Decisiones de diseño

- **¿Por qué no un campo JSON en `League`?** Cada partido cambia de estado y de resultado por su
  cuenta. Con una lista JSON, actualizar un partido obliga a reescribir la lista entera, y dos
  partidos que terminan a la vez se pisan. Además se pierden las foreign keys y las consultas por
  club.
- **¿Por qué no un modelo `Fixture`?** Tendría solo `id` y `league_id`, en relación 1 a 1 con la
  liga. No agrega datos y suma un join. El fixture de una liga es `league.matches`.
- **¿Por qué `MatchParticipation` aparte y no columnas `local_club_id` / `visitante_club_id`?** Cada
  lado tiene sus propios datos (club, roster y más adelante goles), y "partidos del club X" queda
  como un solo filtro. Es el mismo patrón que `FriendlyGame` + `FriendlyGameParticipation`.
- **No confundir con [app/game/models/](../app/game/models/).** Ahí también hay un `Match` y un
  `MatchParticipation`, pero son dataclasses en memoria que usa el motor mientras se juega (pelota,
  posiciones, ticks). Los de `app/models/` son el registro en la base. Se conectan por el id: el
  `Match.id` de la base es el `match_id` del partido en juego.

---

## 4. Flujo del inicio de una liga

```
PATCH /leagues/{league_id}   {"state": "INICIADA"}
   │
   ├─ start_league(...)                         league_service.py
   │     ├─ validaciones (existe, es el creador, estado, mínimo 3 clubes)
   │     ├─ update_state → INICIADA             (flush, sin commit)
   │     ├─ generate_fixture(club_ids, seed)    sorteo en memoria, agrupado en fechas
   │     ├─ crea Match (con match_order y round) + 2 MatchParticipation por par
   │     └─ db.commit()                         todo junto, o rollback de todo
   │
   ├─ broadcast_leagues(db)                     canal de SESIÓN: la lista de ligas muestra INICIADA
   │
   ├─ league_repository.get_by_id(...)          se vuelve a leer la liga, ya con sus partidos
   ├─ build_league_state(db, league)            arma fixture y tabla como schemas
   └─ league_connection_manager.broadcast(...)  canal de LIGA: league_started
```

Si `start_league` lanza una excepción, el endpoint salta directo al `except` y responde 403, 404
o 409. Nunca llega a los broadcasts, así que un inicio rechazado no emite `league_started`.

---

## 5. ¿Por qué parece que el fixture se crea dos veces?

No se crea dos veces. La palabra "fixture" aparece en **tres pasos distintos**, y en cada uno es un
tipo de dato diferente:

| Paso | Dónde | Qué hace | Qué es `fixture` ahí |
|---|---|---|---|
| 1. Sortear | `generate_fixture` en [fixture_service.py](../app/services/fixture_service.py) | Decide quién juega contra quién, en qué fecha y quién es local. No toca la base. | `list[list[tuple[int, int]]]`: una lista por fecha, con pares `(local_club_id, visitante_club_id)`. |
| 2. Guardar | Los dos `for` dentro de `start_league` en [league_service.py](../app/services/league_service.py) | Recorre las fechas y sus pares, y crea **una vez** cada `Match` con su `round` y sus dos participaciones. | La misma lista de fechas del paso 1. |
| 3. Leer y armar | `build_league_state` en [league_service.py](../app/services/league_service.py) | Lee de la base los `Match` ya guardados y los convierte en schemas para mandar. **No crea nada.** | `list[FixtureMatchItem]`: lo que viaja por WebSocket o HTTP. |

El paso 3 se usa en dos lugares, y por eso también puede parecer duplicado:

- en el `PATCH`, para armar el `league_started`,
- en el `GET /leagues/{league_id}`, para quien entra al lobby después.

Los dos solo **leen** lo que guardó el paso 2.

### ¿Por qué separar sortear de guardar?

`generate_fixture` trabaja solo con ids de clubes y no depende de la base. Así los criterios de
cantidad de partidos, pares sin repetir, n−1 partidos por club, fechas válidas y reproducibilidad
con la semilla se testean como una función pura, rápida y sin datos de prueba.

### ¿Por qué el `PATCH` vuelve a leer la liga en vez de reusar lo creado?

`start_league` corre en un thread aparte (`run_in_threadpool`) y termina con `commit()`. Después del
commit, SQLAlchemy marca los objetos como vencidos. Leer la liga de nuevo y armar el payload desde
la base garantiza que lo que se manda es exactamente lo que quedó guardado, con los mismos ids y el
mismo orden que después devuelve el `GET`.

---

## 6. Sorteo (`generate_fixture`)

```python
def generate_fixture(club_ids: list[int], seed: int | None = None) -> list[list[tuple[int, int]]]:
```

Devuelve una lista de **fechas**. Cada fecha es una lista de pares `(local_id, visitante_id)` y
ningún club aparece dos veces en la misma fecha. Se arma con el **método del círculo** (Berger), el
algoritmo clásico para un todos contra todos.

### Pasos

1. `random.Random(seed)` crea un generador propio. Con la misma semilla, el sorteo es el mismo.
2. `ids = sorted(club_ids)` y después `rng.shuffle(ids)`. El `sorted` hace que el resultado no
   dependa del orden en que llegan los ids desde la base; el `shuffle` sortea quién queda en cada
   posición del círculo. Se trabaja sobre una copia, así que la lista que se recibe no se modifica.
3. Si la cantidad de clubes es impar, se agrega un `None`. El club que se cruza con `None` en una
   fecha queda **libre**. Así siempre se trabaja con una cantidad par, que llamamos `n`.
4. Se arman `n − 1` fechas. En cada una:
   - se empareja la posición `0` con la `n − 1`, la `1` con la `n − 2`, y así hacia el centro
     (`i` sube y `j` baja mientras `j > i`);
   - si alguno de los dos es `None`, el par se saltea;
   - `rng.random() < 0.5` decide si queda `(a, b)` o `(b, a)`. El primero es el local.
5. Después de cada fecha se **rota** la lista: el primer elemento queda fijo y el resto se corre una
   posición, con el último pasando adelante:

   ```python
   fijo = ids[0]
   resto = ids[1:]
   resto = resto[-1:] + resto[:-1]
   ids = [fijo] + resto
   ```

### Ejemplo con 4 clubes

```
Fecha 1: [A, B, C, D]  →  A-D, B-C
Fecha 2: [A, D, B, C]  →  A-C, D-B
Fecha 3: [A, C, D, B]  →  A-B, C-D
```

Cada par aparece una sola vez y en cada fecha juegan todos.

### Cantidades

| | n par | n impar |
|---|---|---|
| Fechas | n − 1 | n |
| Partidos por fecha | n / 2 | (n − 1) / 2, y un club libre |
| Partidos totales | n·(n−1)/2 | n·(n−1)/2 |

En los dos casos hay `n // 2` partidos por fecha (con `n` = cantidad real de clubes).

### Semilla

`start_league` recibe un parámetro `seed: int | None = None`. El endpoint no lo manda, así que en
producción el sorteo es aleatorio. Los tests sí lo pasan.

### Cómo lo usa `start_league`

`start_league` recorre las fechas con dos `for`. El de afuera da el número de fecha, que se guarda
en `Match.round`. `match_order` lleva un contador aparte que no se reinicia entre fechas, así queda
numerado 1, 2, 3… en todo el fixture:

```python
order = 1
for round_number, fecha in enumerate(fixture, start=1):
    for local_id, visitante_id in fecha:
        match = Match(..., match_order=order, round=round_number)
        ...
        order += 1
```

Con 4 clubes queda `match_order` 1 a 6 y `round` `[1, 1, 2, 2, 3, 3]`.

---

## 7. Transacción y rollback

Todo lo de `start_league` ocurre dentro de un mismo `try`:

```python
try:
    ...validaciones...
    league_repository.update_state(...)     # flush
    ...crear Match y MatchParticipation...  # db.add
    db.commit()                             # hace el flush y confirma
except Exception:
    db.rollback()
    raise
```

- Ningún repositorio hace `commit()`; solo `add` y `flush`. El único commit es el del final.
- No hace falta un `db.flush()` antes del `commit()`: el `commit()` primero manda a la base todo lo
  pendiente y después confirma. El `flush` solo sirve cuando se necesita que la base vea los cambios
  **antes** de confirmar (por ejemplo, para leer un id generado), y acá los ids salen de la secuencia.
- Si cualquier paso falla, por ejemplo la secuencia de ids en el tercer partido, el `rollback()`
  deshace el cambio de estado y los partidos ya agregados. La liga queda en `POR_COMENZAR`.

---

## 8. Contratos

### Evento `league_started` (canal `ws/league/{league_id}`)

Lo reciben solo los usuarios conectados al canal de esa liga.

```json
{
  "type": "league_started",
  "league_id": 10,
  "fixture": [
    {
      "match_id": 57,
      "match_order": 1,
      "round": 1,
      "state": "POR_COMENZAR",
      "local": { "club_id": 3, "name": "Club 3" },
      "visitante": { "club_id": 1, "name": "Club 1" }
    }
  ],
  "standings": [
    {
      "club_id": 1,
      "name": "Club 1",
      "points": 0,
      "matches_played": 0,
      "matches_won": 0,
      "matches_drawn": 0,
      "matches_lost": 0,
      "goals_for": 0,
      "goals_against": 0,
      "goal_difference": 0
    }
  ]
}
```

El campo `type` le sirve al front para distinguir este evento de los demás que llegan por el
mismo canal (`lobby_state`, `user_joined`, `user_left`).

### `GET /leagues/{league_id}`

| Request | Respuestas |
|---|---|
| `Authorization: Bearer {token}` | `200 OK` con `LeagueDetail` · `401 Unauthorized` · `404 Not Found`: `"League does not exist"` |

`LeagueDetail` tiene `league_id`, `name`, `state`, `privacy`, `current_participants`, `capacity`,
`fixture` y `standings`. Los dos últimos vienen llenos solo cuando la liga está `INICIADA`; si no,
vienen en `null`.

---

## 9. Migración

- Crea `matches` y `match_participations`, junto con los tipos enum `match_state` y `match_role`.
- Una segunda migración agrega la columna `round` a `matches` con el check `ck_match_round_positive`.
  El `--autogenerate` de Alembic detecta la columna pero **no** el check, así que ese se agrega a mano.
- El `downgrade` borra las tablas **y además** los tipos enum, porque en Postgres `drop_table` no
  los borra. Sin eso, un `downgrade` seguido de un `upgrade` falla con
  `type "match_state" already exists`.
- Si tu base local ya tiene esos tipos sueltos, de un intento anterior sin este arreglo, borralos
  una vez con `DROP TYPE match_role; DROP TYPE match_state;` antes de correr `alembic upgrade head`.

---

## 10. Tests

| Archivo | Tipo | Qué cubre |
|---|---|---|
| `tests/test_fixture_service.py` | Unitario, sin base | n·(n−1)/2 partidos, pares sin repetir, nadie contra sí mismo, n−1 partidos por club, misma semilla con el mismo fixture, localía sorteada. Fechas: n−1 fechas si n es par y n si es impar, ningún club juega dos veces en la misma fecha, y con n impar cada club queda libre exactamente una vez. |
| `tests/test_start_league_integration.py` | Integración contra SQLite | Partidos guardados en `POR_COMENZAR` con una participación `LOCAL` y otra `VISITANTE`, roster de la liga, fixture guardado igual al sorteado (aplanando las fechas), `round` guardado igual a la fecha sorteada, tabla en 0, rollback que deja la liga intacta, `get_league_detail` antes y después de iniciar. |
| `tests/test_get_league_api.py` | API con mocks | `GET /leagues/{id}`: 200 con y sin fixture, 404 y 401. |
| `tests/test_league_started_broadcast.py` | API + manager real | Los clientes de la liga reciben `league_started`, los de otra liga no, un inicio rechazado no emite nada, el evento sale después de iniciar y el payload se serializa a JSON. |

En `test_fixture_service.py`, el helper `all_matches` aplana las fechas en una sola lista. Lo usan
los tests que revisan el fixture completo; los de fechas usan `generate_fixture` directamente.

Dos detalles de los tests de integración:

- `get_next_match_id` se reemplaza con `monkeypatch` por un `itertools.count(1)`, porque
  `nextval('match_id_seq')` solo existe en Postgres y los tests corren sobre SQLite.
- Al crear la liga de prueba se hace `db.commit()` y no `flush()`. En producción la liga ya está
  confirmada antes del `PATCH`. Si no se confirma, el `rollback()` de `start_league` también borra la
  liga de prueba. El fixture `db` trabaja con savepoints, así que igual se descarta todo al final del
  test.

---

## 11. Integración con el front

Esta sección es la base para que el front implemente su parte: qué endpoints usa, qué mensajes le
llegan, en qué orden y qué hay que acordar antes de arrancar.

### 11.1 Qué usa el front

| Para qué | Cómo |
|---|---|
| Entrar al lobby de la liga | WebSocket `ws://<host>/ws/league/{league_id}?token=<jwt>` |
| Iniciar la liga (solo el creador) | `PATCH /leagues/{league_id}` con body `{"state": "INICIADA"}` |
| Ver fixture y tabla si se entra después del inicio, o al reconectar | `GET /leagues/{league_id}` |
| Ver la lista de ligas con su estado | WebSocket de sesión `ws/sessions` (ya existente) |

### 11.2 Mensajes del canal de liga

Todos los mensajes del canal `ws/league/{league_id}` traen un campo `type`. El front tiene que
mirar `type` y decidir qué hacer con cada mensaje:

| `type` | Cuándo llega | Qué debería hacer el front |
|---|---|---|
| `lobby_state` | Apenas se conecta | Dibujar el lobby: participantes, creador y estado. |
| `user_joined` | Se une un club | Agregar el club a la lista. |
| `user_left` | Se va un club | Sacar el club de la lista. |
| `league_started` | El creador inició la liga | Pasar a la vista de liga iniciada con el fixture y la tabla del payload, sin recargar. |

El evento `league_started` también le llega al creador, si está conectado al canal. El front no
necesita armar el fixture a partir de la respuesta del `PATCH`, que es un `204` sin cuerpo: alcanza
con escuchar el evento.

### 11.3 Tipos de datos

Referencia en TypeScript de lo que manda el backend, para que el front arme sus tipos:

```ts
type MatchState = "POR_COMENZAR" | "JUGANDO" | "FINALIZADO";
type LeagueState = "POR_COMENZAR" | "INICIADA" | "FINALIZADA";
type LeaguePrivacy = "PUBLICA" | "PRIVADA";

interface FixtureClub {
  club_id: number;
  name: string;
}

interface FixtureMatchItem {
  match_id: number;      // el mismo id que se usará en el WebSocket del partido
  match_order: number;   // posición en el fixture, empieza en 1
  round: number;         // fecha a la que pertenece, empieza en 1
  state: MatchState;
  local: FixtureClub;
  visitante: FixtureClub;
}

interface StandingRow {
  club_id: number;
  name: string;
  points: number;
  matches_played: number;
  matches_won: number;
  matches_drawn: number;
  matches_lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
}

// mensajes del lobby (ya existían, de SCRUM-163)
interface LeagueLobbyUser {
  club_id: number;
  user_name: string;     // es el nombre del club
  avatar: string;
  is_creator: boolean;
}

interface LeagueLobbyState {
  type: "lobby_state";
  league_id: number;
  state: LeagueState;
  current_users: number;
  users: LeagueLobbyUser[];
}

interface LeagueUserEvent {
  type: "user_joined" | "user_left";
  league_id: number;
  user: LeagueLobbyUser;
}

interface LeagueStartedEvent {
  type: "league_started";
  league_id: number;
  fixture: FixtureMatchItem[];
  standings: StandingRow[];
}

// respuesta de GET /leagues/{league_id}
interface LeagueDetail {
  league_id: number;
  name: string;
  state: LeagueState;
  privacy: LeaguePrivacy;
  current_participants: number;
  capacity: number;
  fixture: FixtureMatchItem[] | null;   // null mientras la liga no está INICIADA
  standings: StandingRow[] | null;
}

// todo lo que puede llegar por ws/league/{league_id}
type LeagueChannelMessage = LeagueLobbyState | LeagueUserEvent | LeagueStartedEvent;
```

Reglas para mostrar los datos:

- El fixture llega ordenado por `match_order`, que sigue el orden de las fechas. El front puede
  mostrarlo tal cual.
- Para separar o pintar las fechas, el front agrupa por `round`. Los partidos de una misma fecha
  llegan seguidos.
- `local` y `visitante` ya vienen sorteados. El front no tiene que decidir la localía.
- `goal_difference` ya viene calculada. El front no tiene que hacer la cuenta.
- `standings` puede llegar sin ordenar. Hoy todo está en 0; cuando haya resultados, conviene que el
  front ordene por `points` y después por `goal_difference`, o acordar que lo haga el backend
  (ver 11.8).
- Los nombres de los campos están en inglés (`matches_played` y no `PJ`). Las abreviaturas son solo
  para mostrar.

### 11.4 Errores

**Al conectarse al canal de liga** (código de cierre del WebSocket):

| Código | Motivo |
|---|---|
| `4401` | Falta el token, o es inválido o está vencido. |
| `4403` | El usuario no tiene club, o su club no participa en la liga. |
| `4404` | La liga no existe. |

**Al iniciar la liga** (`PATCH /leagues/{league_id}`):

| Código | Motivo |
|---|---|
| `204` | Liga iniciada. El fixture llega por el evento `league_started`. |
| `401` | Sin token. |
| `403` | El usuario no es el creador. |
| `404` | La liga no existe. |
| `409` | La liga ya fue iniciada, el estado pedido no es `INICIADA`, o hay menos de 3 participantes. |
| `422` | Body inválido. |

En todos los errores el campo `detail` trae el motivo. Si el `PATCH` falla, no se emite
`league_started`, así que el front puede dejar el lobby como estaba y mostrar el error.

**Al consultar la liga** (`GET /leagues/{league_id}`): `200`, `401` o `404`.

### 11.5 Secuencias

**Usuario en el lobby cuando el creador inicia la liga:**

```
front                              backend
  │── conecta ws/league/10 ──────────▶│
  │◀──────────── lobby_state ─────────│
  │        ... (otros user_joined) ...│
  │                                   │◀── PATCH /leagues/10 (creador)
  │◀────────── league_started ────────│   con fixture y tabla
  │   muestra fixture y tabla         │
```

**Usuario que entra después del inicio, o que se reconecta:**

```
front                              backend
  │── GET /leagues/10 ───────────────▶│
  │◀── 200 LeagueDetail ──────────────│   fixture y tabla llenos (state INICIADA)
  │── conecta ws/league/10 ──────────▶│   (para los eventos que vengan después)
```

Si la conexión se corta justo cuando se inicia la liga, el evento se pierde: el backend no reenvía
mensajes. Por eso, al reconectar, el front debería pedir el `GET` para quedar al día.

**Lista de ligas:** al iniciarse una liga, el WebSocket de sesión vuelve a mandar la lista de ligas,
y esa liga aparece con `state: "INICIADA"`. El front puede usarlo para actualizar la lista general.

### 11.6 Payloads completos de ejemplo

Son ejemplos reales del sorteo con 4 clubes (3 fechas de 2 partidos). Los ids son de ejemplo. Se
pueden copiar tal cual como mocks.

**`lobby_state`** (al conectarse a `ws/league/10`):

```json
{
  "type": "lobby_state",
  "league_id": 10,
  "state": "POR_COMENZAR",
  "current_users": 4,
  "users": [
    { "club_id": 1, "user_name": "Los Pibes FC", "avatar": "avatar1.png", "is_creator": true },
    { "club_id": 2, "user_name": "Atlético Sur", "avatar": "avatar2.png", "is_creator": false },
    { "club_id": 3, "user_name": "Deportivo Norte", "avatar": "avatar3.png", "is_creator": false },
    { "club_id": 4, "user_name": "Real Barrio", "avatar": "avatar4.png", "is_creator": false }
  ]
}
```

**`user_joined`** (y `user_left`, que es igual cambiando el `type`):

```json
{
  "type": "user_joined",
  "league_id": 10,
  "user": { "club_id": 4, "user_name": "Real Barrio", "avatar": "avatar4.png", "is_creator": false }
}
```

**Iniciar la liga** (lo manda solo el creador):

```http
PATCH /leagues/10
Authorization: Bearer <jwt>
Content-Type: application/json

{ "state": "INICIADA" }
```

Respuesta: `204 No Content`, sin cuerpo. Si falla, viene un JSON con `detail`:

| Código | `detail` |
|---|---|
| `403` | `"Only the league creator can start the league"` |
| `404` | `"League does not exist"` |
| `409` | `"League cannot be started"` (ya estaba iniciada) |
| `409` | `"Invalid state transition"` (el body no pidió `INICIADA`) |
| `409` | `"League does not have enough participants"` (menos de 3) |

**`league_started`** (le llega a todos los conectados a `ws/league/10`, incluido el creador):

```json
{
  "type": "league_started",
  "league_id": 10,
  "fixture": [
    {
      "match_id": 101, "match_order": 1, "round": 1, "state": "POR_COMENZAR",
      "local": { "club_id": 3, "name": "Deportivo Norte" },
      "visitante": { "club_id": 1, "name": "Los Pibes FC" }
    },
    {
      "match_id": 102, "match_order": 2, "round": 1, "state": "POR_COMENZAR",
      "local": { "club_id": 2, "name": "Atlético Sur" },
      "visitante": { "club_id": 4, "name": "Real Barrio" }
    },
    {
      "match_id": 103, "match_order": 3, "round": 2, "state": "POR_COMENZAR",
      "local": { "club_id": 3, "name": "Deportivo Norte" },
      "visitante": { "club_id": 4, "name": "Real Barrio" }
    },
    {
      "match_id": 104, "match_order": 4, "round": 2, "state": "POR_COMENZAR",
      "local": { "club_id": 2, "name": "Atlético Sur" },
      "visitante": { "club_id": 1, "name": "Los Pibes FC" }
    },
    {
      "match_id": 105, "match_order": 5, "round": 3, "state": "POR_COMENZAR",
      "local": { "club_id": 2, "name": "Atlético Sur" },
      "visitante": { "club_id": 3, "name": "Deportivo Norte" }
    },
    {
      "match_id": 106, "match_order": 6, "round": 3, "state": "POR_COMENZAR",
      "local": { "club_id": 1, "name": "Los Pibes FC" },
      "visitante": { "club_id": 4, "name": "Real Barrio" }
    }
  ],
  "standings": [
    { "club_id": 1, "name": "Los Pibes FC", "points": 0, "matches_played": 0, "matches_won": 0, "matches_drawn": 0, "matches_lost": 0, "goals_for": 0, "goals_against": 0, "goal_difference": 0 },
    { "club_id": 2, "name": "Atlético Sur", "points": 0, "matches_played": 0, "matches_won": 0, "matches_drawn": 0, "matches_lost": 0, "goals_for": 0, "goals_against": 0, "goal_difference": 0 },
    { "club_id": 3, "name": "Deportivo Norte", "points": 0, "matches_played": 0, "matches_won": 0, "matches_drawn": 0, "matches_lost": 0, "goals_for": 0, "goals_against": 0, "goal_difference": 0 },
    { "club_id": 4, "name": "Real Barrio", "points": 0, "matches_played": 0, "matches_won": 0, "matches_drawn": 0, "matches_lost": 0, "goals_for": 0, "goals_against": 0, "goal_difference": 0 }
  ]
}
```

**`GET /leagues/10`** con la liga ya iniciada: `200 OK`.

```json
{
  "league_id": 10,
  "name": "Liga de los jueves",
  "state": "INICIADA",
  "privacy": "PUBLICA",
  "current_participants": 4,
  "capacity": 8,
  "fixture": [ "... igual que en league_started ..." ],
  "standings": [ "... igual que en league_started ..." ]
}
```

**`GET /leagues/10`** con la liga todavía sin iniciar: `200 OK`, con `fixture` y `standings` en `null`.

```json
{
  "league_id": 10,
  "name": "Liga de los jueves",
  "state": "POR_COMENZAR",
  "privacy": "PUBLICA",
  "current_participants": 4,
  "capacity": 8,
  "fixture": null,
  "standings": null
}
```

### 11.7 Mostrar las fechas

- Los partidos de una fecha comparten el mismo `round` y llegan seguidos, en orden de `match_order`.
- Cada fecha tiene siempre `cantidad_de_clubes // 2` partidos.
- **Cantidad impar de clubes:** cada fecha tiene un club que **no juega** (queda libre). No llega
  ningún partido para él en esa fecha. Si el front quiere mostrar "Libre: X", lo calcula como los
  clubes de `standings` que no aparecen en los partidos de ese `round`.

| Clubes | Fechas | Partidos por fecha | Partidos totales | Libre por fecha |
|---|---|---|---|---|
| 3 | 3 | 1 | 3 | 1 club |
| 4 | 3 | 2 | 6 | ninguno |
| 5 | 5 | 2 | 10 | 1 club |
| 6 | 5 | 3 | 15 | ninguno |
| 8 | 7 | 4 | 28 | ninguno |

Ejemplo en TypeScript para agrupar por fecha y calcular el club libre:

```ts
function groupByRound(fixture: FixtureMatchItem[]): Map<number, FixtureMatchItem[]> {
  const rounds = new Map<number, FixtureMatchItem[]>();
  for (const match of fixture) {
    const list = rounds.get(match.round) ?? [];
    list.push(match);
    rounds.set(match.round, list);
  }
  return rounds;   // el Map respeta el orden de inserción: fecha 1, 2, 3...
}

function freeClubs(matches: FixtureMatchItem[], standings: StandingRow[]): StandingRow[] {
  const playing = new Set(matches.flatMap(m => [m.local.club_id, m.visitante.club_id]));
  return standings.filter(row => !playing.has(row.club_id));
}

// uso
for (const [round, matches] of groupByRound(event.fixture)) {
  // dibujar "Fecha {round}" con sus partidos
  // y, si hay, freeClubs(matches, event.standings) como "Libre"
}
```

Y para recibir los mensajes del canal:

```ts
socket.onmessage = (e) => {
  const msg = JSON.parse(e.data) as LeagueChannelMessage;
  switch (msg.type) {
    case "lobby_state":    /* dibujar lobby */ break;
    case "user_joined":    /* agregar msg.user */ break;
    case "user_left":      /* sacar msg.user */ break;
    case "league_started": /* mostrar groupByRound(msg.fixture) y msg.standings */ break;
  }
};
```

### 11.8 Puntos a acordar con el front

Conviene repasar esta lista en una reunión corta, con esta sección abierta, antes de que el front
arranque:

| # | Tema | Propuesta del backend |
|---|---|---|
| 1 | Valor del body del `PATCH` | `{"state": "INICIADA"}`. [API.md](API.md) dice `"in_progress"`: hay que actualizarlo. |
| 2 | Endpoint de fixture y tabla | Todo junto en `GET /leagues/{id}`. API.md los lista separados (`/table` y `/fixture`). Elegir uno y actualizar API.md. |
| 3 | Nombres de campos | Los de la sección 11.3, en inglés. Si el front prefiere otros, cambiarlos ahora y no después. |
| 4 | Orden de la tabla | Definir si ordena el backend o el front, y el criterio de desempate (puntos → diferencia de gol → goles a favor). |
| 5 | Fechas | Cada partido trae `round` y el fixture viaja como lista plana ordenada por fecha. Falta decidir si las fechas se juegan en paralelo o en secuencia. |
| 6 | Ligas privadas | Si el `GET` de una liga privada pide contraseña o solo se permite a participantes. |
| 7 | Ligas finalizadas | Si el `GET` devuelve el fixture también cuando la liga está `FINALIZADA`. |
| 8 | Avatar en fixture y tabla | Hoy solo viajan `club_id` y `name`. Si el front quiere mostrar escudos, hay que agregar `avatar`. |

Para probar sin esperar al backend, el front puede usar los JSON de la sección 11.6 como mocks.

---

## 12. Pendientes y decisiones abiertas

| Tema | Estado |
|---|---|
| Fechas | Resuelto: fixture en fechas con el método del círculo, guardadas en `Match.round` y enviadas al front en `FixtureMatchItem.round`. Falta definir si las fechas se juegan en paralelo o en secuencia. |
| Ejecución de partidos | Correr los partidos, actualizar la tabla al terminar y avanzar de fecha corresponde a otro ticket. Cada partido levanta su propio pool de 6 procesos de comportamiento. |
| Ligas privadas en el `GET` | Hoy cualquier usuario autenticado puede consultar cualquier liga. [API.md](API.md) pide contraseña para ver una privada. |
| Ligas finalizadas | El `GET` devuelve fixture solo con `INICIADA`, como dice el ticket. Probablemente convenga mostrarlo también en `FINALIZADA`. |
| Diferencia con [API.md](API.md) | API.md lista `GET /leagues/{id}/table` y `GET /leagues/{id}/fixture` por separado. Este ticket los devuelve juntos en `GET /leagues/{id}`. Hay que actualizar API.md o acordar el contrato con el front. |
| Orden de la tabla | `standings` sale en el orden en que la base devuelve las participaciones. Con todo en 0 no importa; cuando se actualice la tabla habrá que ordenar por puntos y diferencia de gol. |
