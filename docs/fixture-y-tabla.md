# Fixture y tabla de posiciones al iniciar una liga

Este documento explica qué se hizo en la rama del ticket **SCRUM-146** (generación de la tabla de
posiciones y sorteo del fixture al iniciar una liga): qué modelos se agregaron, cómo fluye el inicio
de una liga, cómo se avisa por WebSocket y qué cubren los tests.

Se apoya en el endpoint de inicio de liga de **SCRUM-141** (`PATCH /leagues/{league_id}`) y en el
WebSocket de liga de **SCRUM-163** (`ws/league/{league_id}`).

---

## 1. Qué pide el ticket

| Requisito | Detalle |
|---|---|
| Cuándo | Al pasar la liga de `POR_COMENZAR` a `INICIADA`, en la misma operación del `PATCH`. |
| Fixture | Todos contra todos a una sola rueda: con n clubes, n·(n−1)/2 partidos, cada par una sola vez. |
| Partidos | Cada partido es un `Match` en `POR_COMENZAR` con dos `MatchParticipation` (`LOCAL` y `VISITANTE`). |
| Sorteo | Se sortean el orden de los partidos y la localía. Acepta una semilla opcional para los tests. |
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
| Sorteo | [app/services/fixture_service.py](../app/services/fixture_service.py) | `generate_fixture(club_ids, seed)`. |
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
| `match_order` | int \| null | Posición del partido en el fixture sorteado (empieza en 1). |

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
   │     ├─ generate_fixture(club_ids, seed)    sorteo en memoria
   │     ├─ crea Match + 2 MatchParticipation por par
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
| 1. Sortear | `generate_fixture` en [fixture_service.py](../app/services/fixture_service.py) | Decide quién juega contra quién, en qué orden y quién es local. No toca la base. | `list[tuple[int, int]]`: pares `(local_club_id, visitante_club_id)`. |
| 2. Guardar | El `for` dentro de `start_league` en [league_service.py](../app/services/league_service.py) | Recorre esos pares y crea **una vez** cada `Match` con sus dos participaciones. | La misma lista de tuplas del paso 1. |
| 3. Leer y armar | `build_league_state` en [league_service.py](../app/services/league_service.py) | Lee de la base los `Match` ya guardados y los convierte en schemas para mandar. **No crea nada.** | `list[FixtureMatchItem]`: lo que viaja por WebSocket o HTTP. |

El paso 3 se usa en dos lugares, y por eso también puede parecer duplicado:

- en el `PATCH`, para armar el `league_started`,
- en el `GET /leagues/{league_id}`, para quien entra al lobby después.

Los dos solo **leen** lo que guardó el paso 2.

### ¿Por qué separar sortear de guardar?

`generate_fixture` trabaja solo con ids de clubes y no depende de la base. Así los criterios de
cantidad de partidos, pares sin repetir, n−1 partidos por club y reproducibilidad con la semilla se
testean como una función pura, rápida y sin datos de prueba.

### ¿Por qué el `PATCH` vuelve a leer la liga en vez de reusar lo creado?

`start_league` corre en un thread aparte (`run_in_threadpool`) y termina con `commit()`. Después del
commit, SQLAlchemy marca los objetos como vencidos. Leer la liga de nuevo y armar el payload desde
la base garantiza que lo que se manda es exactamente lo que quedó guardado, con los mismos ids y el
mismo orden que después devuelve el `GET`.

---

## 6. Sorteo (`generate_fixture`)

```python
def generate_fixture(club_ids: list[int], seed: int | None = None) -> list[tuple[int, int]]:
```

1. `random.Random(seed)` crea un generador propio. Con la misma semilla, el sorteo es el mismo.
2. `combinations(sorted(club_ids), 2)` da todos los pares sin repetir. El `sorted` hace que el
   resultado no dependa del orden en que llegan los ids desde la base.
3. `rng.shuffle(pares)` sortea el orden de los partidos.
4. Para cada par, `rng.random() < 0.5` decide si queda `(a, b)` o `(b, a)`. El primero es el local.

`start_league` recibe un parámetro `seed: int | None = None`. El endpoint no lo manda, así que en
producción el sorteo es aleatorio. Los tests sí lo pasan.

---

## 7. Transacción y rollback

Todo lo de `start_league` ocurre dentro de un mismo `try`:

```python
try:
    ...validaciones...
    league_repository.update_state(...)     # flush
    ...crear Match y MatchParticipation...  # db.add
    db.commit()
except Exception:
    db.rollback()
    raise
```

- Ningún repositorio hace `commit()`; solo `add` y `flush`. El único commit es el del final.
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
- El `downgrade` borra las tablas **y además** los tipos enum, porque en Postgres `drop_table` no
  los borra. Sin eso, un `downgrade` seguido de un `upgrade` falla con
  `type "match_state" already exists`.
- Si tu base local ya tiene esos tipos sueltos, de un intento anterior sin este arreglo, borralos
  una vez con `DROP TYPE match_role; DROP TYPE match_state;` antes de correr `alembic upgrade head`.

---

## 10. Tests

| Archivo | Tipo | Qué cubre |
|---|---|---|
| `tests/test_fixture_service.py` | Unitario, sin base | n·(n−1)/2 partidos, pares sin repetir, nadie contra sí mismo, n−1 partidos por club, misma semilla con el mismo fixture, localía sorteada. |
| `tests/test_start_league_integration.py` | Integración contra SQLite | Partidos guardados en `POR_COMENZAR` con una participación `LOCAL` y otra `VISITANTE`, roster de la liga, fixture guardado igual al sorteado, tabla en 0, rollback que deja la liga intacta, `get_league_detail` antes y después de iniciar. |
| `tests/test_get_league_api.py` | API con mocks | `GET /leagues/{id}`: 200 con y sin fixture, 404 y 401. |
| `tests/test_league_started_broadcast.py` | API + manager real | Los clientes de la liga reciben `league_started`, los de otra liga no, un inicio rechazado no emite nada, el evento sale después de iniciar y el payload se serializa a JSON. |

Dos detalles de los tests de integración:

- `get_next_match_id` se reemplaza con `monkeypatch` por un `itertools.count(1)`, porque
  `nextval('match_id_seq')` solo existe en Postgres y los tests corren sobre SQLite.
- Al crear la liga de prueba se hace `db.commit()` y no `flush()`. En producción la liga ya está
  confirmada antes del `PATCH`. Si no se confirma, el `rollback()` de `start_league` también borra la
  liga de prueba. El fixture `db` trabaja con savepoints, así que igual se descarta todo al final del
  test.

---

## 11. Pendientes y decisiones abiertas

| Tema | Estado |
|---|---|
| Fechas | El fixture actual es una lista plana. Se propuso organizarlo en fechas jugadas en paralelo (método del círculo, con un club libre cuando n es impar). Falta que el equipo lo apruebe; si se aprueba, se agrega una columna `round` en `Match` y cambia `generate_fixture`. |
| Ejecución de partidos | Correr los partidos, actualizar la tabla al terminar y avanzar de fecha corresponde a otro ticket. Cada partido levanta su propio pool de 6 procesos de comportamiento. |
| Ligas privadas en el `GET` | Hoy cualquier usuario autenticado puede consultar cualquier liga. [API.md](API.md) pide contraseña para ver una privada. |
| Ligas finalizadas | El `GET` devuelve fixture solo con `INICIADA`, como dice el ticket. Probablemente convenga mostrarlo también en `FINALIZADA`. |
| Diferencia con [API.md](API.md) | API.md lista `GET /leagues/{id}/table` y `GET /leagues/{id}/fixture` por separado. Este ticket los devuelve juntos en `GET /leagues/{id}`. Hay que actualizar API.md o acordar el contrato con el front. |
| Orden de la tabla | `standings` sale en el orden en que la base devuelve las participaciones. Con todo en 0 no importa; cuando se actualice la tabla habrá que ordenar por puntos y diferencia de gol. |
| `db.flush()` en `start_league` | Hay un `flush()` justo antes del `commit()` que sobra, porque el commit ya hace el flush. No rompe nada. |
