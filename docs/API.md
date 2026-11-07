## REST

|   | Categoría | Nombre | Endpoints | Query params | Headers | Request Body | Response |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Autenticación y Sesión | Registrar usuario | POST /users |  | Content-Type: application/json | {"email": string, "password": string, "club_name" : string ,"avatar" : string} | (201 Created) : {}<br>(400 Bad request): {response: "Required parameters are missing or incorrect."}<br>(400 Bad request): {response: "Email already used."} |
| 2 | Autenticación y Sesión | Iniciar sesión | POST /sessions |  | Content-Type: application/json | { "email": "string", "password": "string" } | (200 OK): { "token": "string" }<br>(401 Unauthorized"}<br> |
| 3 | Autenticación y Sesión | Cerrar sesión | DELETE /sessions/me |  | Authorization: Bearer {token}, Content-Type: application/json |  | (200 OK)<br>(401 Unauthorized) |
| 4 | Autenticación y Sesión | cambiar contraseña | PATCH /users/me |  | Authorization: Bearer {token}, Content-Type: application/json | {"old_password": string, "new_password" : string}<br> | (204 No Content)<br>(401 Unauthorized)<br>(400 Bad request) {response : "The old password is incorrect.}<br><br> |
|  | Autenticación y Sesión | Ver usuario | GET /users/me |  | Authorization: Bearer {token} |  | (200 OK) "user_name": string, "user_email" : string<br>(401 Unauthorized) |
| 5 | Administración club/perfil<br> | Ver club propio | GET /clubes/me |  | Authorization: Bearer {token} |  | (200 OK): {"club_avatar": string, "club_name" : string ,"club_stats": JSON}<br>(401 Unauthorized) |
| 6 | Administración club/perfil<br> | Ver club ajeno | GET /clubes/{id} |  | Authorization: Bearer {token} |  | (200 OK)  { "user_name": string, "user_email" : string, "club_avatar": string, "club_name" : string ,"club_stats": JSON}<br>(401 Unauthorized)<br>(404 Not found) : {response : "Club not founded."} |
| 7 | Administración club/perfil<br> | Crear jugador | POST /clubes/me/players |  | Authorization: Bearer {token}, Content-Type: application/json | { "name": "string", "power": "int", "agility": "int", "control": "int", "speed": "int", "strength": "int" } | (201 Created): { "id_jugador": "int", "status": "Player created" }<br>(400 Bad Request): {response: "Missing required data or attributes to fully define the player."}<br>(401 Unauthorized) |
| 8 | Administración club/perfil<br> | Ver jugadores creados | GET /clubes/me/players |  | Authorization: Bearer {token} |  | (200 OK): [<br>  {<br>    "id": int,<br>    "name": string,<br>    "power": int,<br>    "agility": int,<br>    "control": int,<br>    "speed": int,<br>    "strength": int<br>  },<br>  ...<br>]<br>(401 Unauthorized) |
| 9 | Administración club/perfil<br> | Buscar jugador | GET /clubes/me/players | ?name={str} | Authorization: Bearer {token} |  | (200 OK): { "players_list": {{"id_jugador": int, "name" : string, "PACSS" : JSON}}, ... }<br>(401 Unauthorized) |
|  | Administración club/perfil<br> | Obtener jugador por ID | GET /clubes/me/players/{player_id} |  |  |  | (200 OK): { {{"id_jugador": int, "name" : string}<br>(401 Unauthorized)<br>(404 Not Found) {"error": "Jugador no encontrado" }<br>(400 Bad Request) {"error": "El parámetro ID debe ser un número entero válido"<br>500 Internal Server Error: {"detail":"Player could not be created"}. |
| 10 | Administración club/perfil<br> | Eliminar jugador | DELETE /clubes/me/players/{id} |  | Authorization: Bearer {token} |  | (204 No content)<br>(403 Forbidden) : {response : "User cannot perform this action while playing a live match."}<br>(401 Unauthorized)<br>(404 Not Found) : {response : "The player doesn't exist"} |
|  | Administración club/perfil<br> | Validar código de comportamiento | POST /clubes/me/behaviors/validate |  | Authorization: Bearer {token}, Content-Type: application/json | { "code": "string" } | (200 OK): { "valid": true }<br>(400 Bad Request): { "detail": "string" }<br>(401 Unauthorized) |
| 11 | Administración club/perfil<br> | Crear comportamiento | POST /clubes/me/behaviors |  | Authorization: Bearer {token}, Content-Type: application/json | { "name": "string", "code": "string" } | (201 Created): { "behavior_id": int }<br>(400 Bad Request): { "detail": "string" }<br>(401 Unauthorized) |
| 12 | Administración club/perfil<br> | Ver comportamientos disponibles | GET /clubes/me/behaviors |  | Authorization: Bearer {token} |  | (200 OK): [ { "behavior_id": int, "name": "string", "code": "string", "is_default": bool }, ... ]<br>(400 Bad Request): { "detail": "User does not have a club" }<br>(401 Unauthorized) |
| 13 | Administración club/perfil<br> | Buscar comportamiento por nombre | GET /clubes/me/behaviors | ?name={str} | Authorization: Bearer {token} |  | (200 OK): { "behavior_id": int, "code": "string" }<br>(400 Bad Request): { "detail": "User does not have a club" }<br>(401 Unauthorized)<br>(404 Not Found): { "detail": "Behavior not found" } |
|  | Administración club/perfil<br> | Obtener comportamiento por ID | GET /clubes/me/behaviors/{behavior_id} |  | Authorization: Bearer {token} |  | (200 OK): { "behavior_id": int, "name": "string", "code": "string", "is_default": bool }<br>(400 Bad Request): { "detail": "User does not have a club" }<br>(401 Unauthorized)<br>(404 Not Found): { "detail": "Behavior not found" } |
| 14 | Administración club/perfil<br> | Editar comportamiento | PUT /clubes/me/behaviors/{behavior_id} |  | Authorization: Bearer {token}, Content-Type: application/json | { "name": "string", "code": "string" } | (204 No Content)<br>(400 Bad Request): { "detail": "string" }<br>(401 Unauthorized)<br>(403 Forbidden): { "detail": "Default behaviors cannot be modified" }<br>(404 Not Found): { "detail": "Behavior not found" } |
| 15 | Administración club/perfil<br> | Eliminar comportamiento | DELETE /clubes/me/behaviors/{behavior_id} |  | Authorization: Bearer {token} |  | (204 No content)<br>(401 Unauthorized)<br>(403 Forbidden) : {response : "User cannot perform this action while playing a live match."}<br>(404 Not found) : {response : "behavior not found.") |
|  | Administración club/perfil<br> | Crear comportamiento DT | POST /clubes/me/coach_behaviors |  | Authorization: Bearer {token}, Content-Type: application/json | { "name": "string", "code": "string" } | (201 Created): { "coach_behavior_id": int, "name": "string", "code": "string" }<br>(400 Bad request) : {response: "Missing required data to fully define the coach behavior."}<br>(400 Bad request) : {detail: "<mensaje que describe el error de validación>"}, por ejemplo "Se debe definir la función principal 'def coach():'", "Error sintáctico en la línea N: ...", "No se permiten importaciones de librerías en el comportamiento", "La función coach() no debe llevar argumentos" o "El comportamiento excedió el tiempo máximo de ejecución (posible bucle infinito)" (ver 11.2)<br>(401 Unauthorized)<br>(403 Forbidden) : {response : "User cannot perform this action while playing a live match."}<br>(409 Conflict) : {response: "Coach behavior name already exists."}<br>(409 Conflict) : {response: "Coach behavior name matches a default behavior."} |
|  | Administración club/perfil<br> | Ver comportamientos DT creados | GET /clubes/me/coach_behaviors |  | Authorization: Bearer {token} |  | (200 OK): [{"coach_behavior_id": int, "name": "string", "code": "string"}, ...]<br>(401 Unauthorized)<br>(404 Not found) : {response : "User does not have a club"} |
|  | Administración club/perfil<br> | Obtener comportamiento DT por ID | GET /clubes/me/coach_behaviors/{coach_behavior_id} |  | Authorization: Bearer {token} |  | (200 OK): {"coach_behavior_id": int, "name": "string", "code": "string"}<br>(401 Unauthorized)<br>(404 Not found) : {response : "Coach behavior not found."}<br>(404 Not found) : {response : "User does not have a club"} |
|  | Administración club/perfil<br> | Eliminar comportamiento DT | DELETE /clubes/me/coach_behaviors/{coach_behavior_id} |  | Authorization: Bearer {token} |  | (204 No content)<br>(401 Unauthorized)<br>(403 Forbidden) : {response : "User cannot perform this action while playing a live match."}<br>(404 Not found) : {response : "Coach behavior not found."} |
| 16 | Administración club/perfil<br> | Renombrar club | PUT /clubes/me |  | Authorization: Bearer {token}, Content-Type: application/json | {"new_name" : string} | (204 No content)<br>(401 Unauthorized)<br>(403 Forbidden) : {response : "User cannot perform this action while playing a live match."}<br>(400 Bad Request): {response: "Club name is not available"} |
| 17 | Administración club/perfil<br> | Cambiar avatar de club | PUT /clubes/me |  | Authorization: Bearer {token}, Content-Type: multipart/form-data | {"new_avatar" : string} | (204 No content)<br>(401 Unauthorized)<br>(400 Bad Request): {response: "Club name is not available."} |
| 18 | Administración club/perfil<br> | Editar plantilla (Default, fuera de sprint 1) | PUT /clubes/me/roster |  | Authorization: Bearer {token}, Content-Type: application/json | {("id_jugador1" : int, "is_starter" : bool, pos_slot: string, behaviour_id: int, ...., "id_jugador6", ..., ),<br>initial_formation: string} | (204 No content)<br>(401 Unauthorized)<br>(400 Bad request) : {response : "An ID's doesn't exist.")<br>(400 Bad Request): {response: "Missing required data to fully edit the line up."} |
|  | Administración club/perfil<br> | Crear plantilla (para cada friendly, para cada liga) | POST /clubes/me/roster |  | Authorization: Bearer {token}, Content-Type: application/json | {<br>  "duration": int,<br>  "roster": {<br>    "formation": string,<br>    "coach_behavior_id": int \| null,<br>    "players": [<br>      {<br>        "player_id": int,<br>        "is_starter": bool,<br>        "slot": string \| null,<br>        "initial_behavior_id": int \| null<br>      }<br>    ]<br>  }<br>} | (201 Created): { roster_id : int, friendly_game_id: int}<br>(204 No content)<br>(401 Unauthorized)<br>(400 Bad request) : {response : "An ID's doesn't exist.")<br>(400 Bad Request): {response: "Missing required data to fully edit the line up."}<br>(400 Bad Request): {response: "Coach behavior doesn't exist."} |
|  | Administración club/perfil<br> | Obtener plantilla  | GET /clubes/me/roster/{roster_id} |  | Authorization: Bearer {token}, Content-Type: application/json | me ffalta la response de este, ahi la hago | (200 ok) : {("id_jugador1" : int, "is_starter" : bool, pos_slot: string, behaviour_id: int, ...., "id_jugador6", ..., ),<br>initial_formation: string}<br>(401 Unauthorized)<br>(400 Bad request) : {response : "An ID's doesn't exist.")<br>(400 Bad Request): {response: "Missing required data to fully edit the line up."} |
| 19 | Administración club/perfil<br> | Ver estadísticas del club | GET /clubes/me |  | Authorization: Bearer {token} |  | (200 OK) : {"TotalPoints": int, "GoalsFor" : int, "GoalsAgainst" : int, "MatchesPlayed" : int, "MatchesWon" : int, "MatchesDrawn" : int, "MatchesLost" : int, "LeaguesPlayed" : int, "LeaguesWon" : int, "FriendliesWon" : int, "FriendliesPlayed" : int}<br>(401 Unauthorized) |
| 20 | Ranking global | Ver el ranking global. | GET /ranking |  | Authorization: Bearer {token} |  | (200 OK) : {{"id_usuario" : int, "ranking_data": JSON}, ...}<br>(401 Unauthorized) |
| 21 | Ranking global | Buscar club en ranking global | GET /ranking/ | ?name={str} | Authorization: Bearer {token} |  | (200 OK) : {{"id_usuario" : int, "datos": JSON}, ...}<br>(401 Unauthorized) |
| 22 | Partidos amistosos  | Crear partido amistoso. | POST /friendly_games |  | Authorization: Bearer {token}, Content-Type: application/json | {<br>  "duration": int,<br>  "roster": {<br>    "formation": string,<br>    "coach_behavior_id": int \| null,<br>    "players": [<br>      {<br>        "player_id": int,<br>        "is_starter": bool,<br>        "slot": string \| null,<br>        "initial_behavior_id": int \| null<br>      }<br>    ]<br>  }<br>} | Response (201 OK): { "friendly_game_id": int, "roster_id": int}<br>(401 Unauthorized)<br>(400 Bad request) : {response : "Datos inválidos") |
| 23 | Partidos amistosos  | Ver partidos amistosos creados | GET /friendly_games |  | Authorization: Bearer {token} |  | (200 OK) : {{"id_friendlyGame": int, "Username": string<br>"matchDuration": Int, "state": enum, "currentUsers" : int}, ...} <br>(401 Unauthorized) |
| 24 | Partidos amistosos  | Obtener datos de un partido amistoso | GET /friendly_games | ?name={str} | Authorization: Bearer {token} |  | (200 OK) : {{"id_friendlyMatch": int, "name": string<br>"matchDuration": Int, "state": enum, "currentUsers" : int}, ...}<br>(401 Unauthorized) |
| 25 | Partidos amistosos  | Iniciar partido amistoso | PATCH /friendly_games/{friendlyGame_id} |  | Authorization: Bearer {token}, Content-Type: application/json | {"state": string} | (200 OK): {match_id: int}<br>(401 Unauthorized)<br>(403 Forbidden) : {"Host cannot start the friendly game alone."}<br>(403 Forbidden) : {"User is not the host of the friendly game."<br>(404 Not Found) : {"Friendly game doesn't exist."} |
| 26 | Partidos amistosos  | Unirse a un partido amistoso | POST /friendly_games/{friendlyGame_id}/users |  | Authorization: Bearer {token}, Content-Type: application/json | {<br>  "roster": {<br>    "formation": stirng.",<br>    "coach_behavior_id": int \| null,<br>    "players": [<br>      {<br>        "player_id": int,<br>        "is_starter": bool,<br>        "slot": "string",<br>        "initial_behavior_id": INT<br>      }<br>    ]<br>  }<br>} | 201 Created<br>400 Bad Request<br>{ "detail": "Invalid roster" }<br>401 Unauthorized<br>{ "detail": "Could not validate credentials" }<br>404 Not Found<br>{ "detail": "Friendly game not found" }<br>409 Conflict<br>{ "detail": "Friendly game not available" }<br>409 Conflict<br>{ "detail": "Friendly game is full" }<br>409 Conflict<br>{ "detail": "User is already participating" } |
| 27 | Partidos amistosos  | Cancelar/Eliminar un partido amistoso | DELETE /friendly_games/{friendlyGame_id} |  | Authorization: Bearer {token} |  | (204 No content)<br>(401 Unauthorized)<br>(403 Forbidden) : {response : "Only host can delete the friendly game"<br>(404 Not Found) : {response : "Friendly game doesn't exists"} |
| 28 | Partidos amistosos  | Abandonar un partido amistoso | DELETE /friendly_games/{fGame_id}/users/me |  | Authorization: Bearer {token} |  | (204 No content)<br>(401 Unauthorized)<br>(404 Not Found) : {response : "Friendly game doesn't exists"}<br>(409 Conflict): {response : "Friendly game already started" |
| 29 | Partido en vivo | Sustituir a un jugador | PUT /live_match/{lmatch_id}/me/{player_id} |  | Authorization: Bearer {token}, Content-Type: application/json | {"new_player": int} | (204 No content) <br>(401 Unauthorized) <br>(404 Not found): {response: Match or player not found}<br>(409 Conflict): {response: Substitution limit reached} |
| 30 | Partido en vivo | Reemplazar comportamiento de un jugador. | PUT /live_match/{lmatch_id}/me/{player_id}/behaviours |  | Authorization: Bearer {token}, Content-Type: application/json | {"new_behaviour": int} | (204 No content) <br>(401 Unauthorized) <br>(400 Bad request) {response: "Missing behaviour id in body request."}<br>(400 Bad request) {response: "behaviour doen't found or doesn't exist"}<br>(400 Bad request) {response: "A behaviour cannot be changed to itself."}<br>(404 Not found): {response: Match or player not found}<br> |
| 31 | Liga  | Ver ligas | GET /leagues |  | Authorization: Bearer {token} |  | (200 OK): {{"id_league": int, "name": String, "matchDuration": Int, "actualPlayersAmount": Int, "state": Enum, "privacy": Enum}, ..., {...}}<br>(401 Unauthorized) <br> |
| 32 | Liga  | Buscar ligas | GET /leagues | ?name={str} | Authorization: Bearer {token} |  | (200 OK): {{"id_league": int, "name": String, "matchDuration": Int, "actualPlayersAmount": Int, "state": Enum, "privacy": Enum}, ..., {...}}<br>(401 Unauthorized) <br> |
| 33 | Liga  | Unirse a una liga pública. | POST /leagues/{league_id}/users |  | Authorization: Bearer {token}, Content-Type: application/json | { "id_league": int } | (200 OK)<br>(401 Unauthorized)<br>(404 Not found) : "League doen't exists" |
| 34 | Liga  | Unirse a una liga privada. | POST /leagues/{league_id}/users |  | Authorization: Bearer {token}, Content-Type: application/json | { "id_league": int, "password": "string" } | (200 OK)<br>(401 Unauthorized)<br>(403 Forbidden): {response: "Incorrect password"}<br>(403 Forbidden) : {response: "League is already full."}<br>(404 Not found) : {response: "League doen't exists"} |
| 35 | Liga  | Ver una liga pública | GET /leagues/{league_id} |  | Authorization: Bearer {token} |  | (200 OK)<br>(401 Unauthorized)<br>(404 Not found) : "League doen't exists" |
| 35 | Liga  | Ver una liga privada | GET /leagues/{league_id} |  | Authorization: Bearer {token}, Content-Type: application/json | {"league_password" : string} | (200 OK)<br>(401 Unauthorized)<br>(403 Forbidden): {response: "Incorrect password"}<br>(404 Not found) : "League doen't exists" |
| 36 | Liga  | Abandonar una liga | DELETE /leagues/{league_id}/users/me |  | Authorization: Bearer {token} |  | (204 Not content)<br>(401 Unauthorized)<br>(403 Foribidden) : {response: "League already started"}<br>(404 Not found) : {response: "League deleated or doesn't exist"}<br>(409 Conflict) : {response: "User is not enrolled in this league"} |
| 37 | Liga  | Crear liga. | POST /leagues |  | Authorization: Bearer {token}, Content-Type: application/json | Request Body: { "nombre": "string", "duracion_partido": "int", "max_usuarios": "int", "es_privada": "boolean", "password": "string" } | (201 Created): { "id_liga": int }<br>(400 Bad request) {response: "Missing body requirement"}<br>(401 Unauthorized) |
| 38 | Liga  | Cancelar liga. | DELETE /leagues/{league_id} |  | Authorization: Bearer {token} |  | (204 No Content)<br>(401 Unauthorized)<br>(403 Forbidden) : {response: "User is not the host of the league"}<br>(404 Not Found) : {response: "League doesn't exist"} |
| 39 | Liga  | Iniciar partida de Liga. | PATCH /leagues/{league_id} |  | Authorization: Bearer {token}, Content-Type: application/json | {"state": "in_progress"} | (204 No Content)<br>(400 Bad Request) : {response: "Missing state or incorrect request body"}<br>(401 Unauthorized)<br>(403 Forbidden) : {response: "User is not the host of the league"}<br>(404 Not Found) : {response: "League doesn't exist"} |
| 40 | Liga  | Consultar la tabla de la Liga. | GET /leagues/{league_id}/table |  | Authorization: Bearer {token} |  | (200 OK): {"league_table" : JSON}<br>(401 Unauthorized)<br>(403 Forbidden) : {response: "The user is not viewer or member of the league."}<br>(404 Not Found) : {response: "League doesn't exist"} |
| 41 | Liga  | Consultar fixture  de la Liga. | GET /leagues/{league_id}/fixture |  | Authorization: Bearer {token} |  | (200 OK): {"fixture": JSON}<br>(401 Unauthorized)<br>(404 Not Found) : {response: "League doesn't exist"}<br>(404 Not Found) : {response: "Fixture doesn't exist yet"} |

## Websocket

| n° | Conexión | Alcance | evento | Nombre de ws | descripción | payload | status code  |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Websocket de sesión | Global | Broadcast de lista de friendly matches y lista de leagues | ws/sessions |  | {<br>  "friendly_games": [<br>    {<br>      "friendly_game_id": int,<br>      "creator_club_name": string,<br>      "current_participants": int,<br>      "capacity": int,<br>      "state": string<br>    }<br>  ]<br>} | 1008 |
| 1 | Websocket sala de espera - Liga | Liga específica | estado_liga | ws/league | El servidor provee cantidad de participantes actuales, estado de liga, tiempo actual de los partidos en vivo?? | {<br>    current_users: int,<br>    users: [<br>        {<br>            user_name: string,<br>            avatar: string<br>        },<br>        ...<br>    ]<br>} | 1000<br>4401<br>4404 |
| 2 | Websocket sala de espera - Partido amistoso | Partido amistoso específico | estado_Partidoamistoso | ws/friendly_game/{friendly_game_id} | El servidor provee cantidad de participantes actuales, estado de partido amistoso | {<br>    friendly_game_id: int,<br>    state: int,<br>    current_users: int,<br>    match_id: int,<br>    users: [<br>        {<br>            user_name: string,<br>            avatar: string,<br>	    is_creator: bool<br>        },<br>        {<br>            user_name: string,<br>            avatar: string,<br>	    is_creator: bool<br>        }<br>    ]<br>} | 1000 cierre normal de lobby<br>4401 token faltante o invalido<br>4404 amistoso inexistente<br>4403 club no participa<br>4409 lobby no disponible<br> |
| 3 | Websocket Partido | Dentro de un partido en vivo | estado_partido | ws/matches/{match_id} | El estado provee la posición matricial (x, y) de la pelota y de cada jugador, junto con las estadísticas de goles y el tiempo transcurrido | {<br>    "actual_tic": int,<br>    "total_tic": int,<br>    "user1_goals": int,<br>    "user2_goals": int,<br>    "ball": {<br>        "x": float,<br>        "y": float,<br>        "speed_x": float,<br>        "speed_y": float<br><br>    },<br>    "players": [<br>        {<br>            "player_id": int,<br>            "x": float,<br>            "y": float <br>            " is_on_field": bool<br>            "team": string ("A" \| "B")<br>        }<br>    ]<br>} | 1000 cierre normal |
| 4 | Websocket Partido | Dentro de un partido en vivo | cambios_dt | ws/matches/{match_id} | El servidor notifica los cambios de comportamiento aplicados por los DT. Se envía al comienzo del tic en el que rigen los cambios (from_tic), antes del estado del partido, y solo si se aplicó al menos un cambio del DT. No incluye asignaciones descartadas ni las reemplazadas por un cambio manual | {<br>    "event": "coach_changes",<br>    "from_tic": int,<br>    "changes": [<br>        {<br>            "club_id": int,<br>            "player_id": int,<br>            "behavior": string<br>        }<br>    ]<br>} | 1000 cierre normal |
| 5 | Websocket Partido | Dentro de un partido en vivo | sustituciones_dt | ws/matches/{match_id} | El servidor notifica las sustituciones pedidas por los DT y ejecutadas en la pausa. Se envía al cerrarse la ventana de sustituciones, solo si se ejecutó al menos una sustitución de un DT. No incluye sustituciones manuales ni pedidos descartados | {<br>    "event": "coach_substitutions",<br>    "changes": [<br>        {<br>            "club_id": int,<br>            "player_out_id": int,<br>            "player_in_id": int<br>        }<br>    ]<br>} | 1000 cierre normal |
                                                              |


# Behavior API

## 1. Overview

Esta API permite definir comportamientos autónomos para los jugadores BOT del juego FUTBOT.

Cada comportamiento se implementa en Python y cada jugador BOT que lo tenga asignado lo ejecuta una vez por cada instante discreto del juego (tic).

Durante cada ejecución, el comportamiento puede hacer uso de primitivas para:

- consultar el estado actual del partido;
- consultar capacidades del jugador BOT que está ejecutando el comportamiento;
- utilizar funciones auxiliares geométricas y físicas;
- devolver exactamente una primitiva de acción para el próximo tic.

Las únicas acciones válidas que puede devolver el comportamiento son:
- `move(...)`
- `kick(...)`
- `wait()`

Las primitivas de consulta de capacidades del jugador BOT utilizan automáticamente el estado y los PACSS del jugador que está ejecutando el comportamiento.

Además de los comportamientos de jugador, la API permite definir comportamientos DT (director técnico), que cambian automáticamente los comportamientos de los jugadores BOT en cancha durante el partido. Se describen en la sección 11.

---

## 2. Behavior entry point

Todo comportamiento debe definir obligatoriamente la función: 

```python
def play():
    ...
```

### `play()`

**Descripción:**
Es el punto de entrada del comportamiento. El servidor ejecuta esta función una vez por tic para cada jugador BOT que tenga asignado el comportamiento.

La función debe devolver exactamente una de las primitivas de acción:

```python
move(...)
kick(...)
wait()
```

Cualquier otro valor de retorno se considera inválido.

### Valid example

```python
def play():
    ball_position, _ = ball()

    if can_kick():
        goal = opponent_goal()
        shot_distance = distance(ball_position, goal)
        shot_direction = direction_to(ball_position, goal)

        return kick(
            shot_direction,
            kick_force_for_distance(shot_direction, shot_distance)
        )

    return wait()
```

### Invalid example

```python
def play():
    return self()
```

`self()` es una primitiva de consulta y no una acción válida.

---

## 3. Basic data types

### `Position`

```python
Position = tuple[float, float]
```

Representa una posición dentro de la cancha.

- Primer componente: coordenada en el eje x
- Segunda componente: coordenada en el eje y

---

### `Direction`

```python
Direction = tuple[float, float]
```

Representa una dirección mediante un vector unitario. Sus componentes pertenecen al intervalo `[-1, 1]` y su magnitud es igual a  `1`. Puede obtenerse mediante la función `direction_to(...)`, aunque el usuario puede construir manualmente un valor de tipo `Direction` siempre que respete dichas restricciones.

Si un valor de tipo `Direction` no cumple estas restricciones, la acción que lo utilice se considerará inválida y no se ejecuta.

Ejemplos:

```python
(1.0, 0.0)     # derecha
(-1.0, 0.0)    # izquierda
(0.0, 1.0)     # arriba
(0.0, -1.0)    # abajo
```

---

### `Velocity`

```python
Velocity = tuple[float, float]
```

Representa una velocidad en el plano de juego. Sus componentes indican la velocidad sobre los ejes X e Y.

Un valor de tipo  `Velocity` no tiene magnitud fija. Su magnitud representa la rapidez del objeto y sus componentes la dirección en la que se mueve.

En la versión actual de la API, este tipo se utiliza para representar la velocidad de la pelota como parte de `BallState`.

---

### `PlayerState`

```python
PlayerState = tuple[int, Position]
```

Representa el identificador y la posición actual de un jugador.

---

### `BallState`

```python
BallState = tuple[Position, Velocity]
```

Representa el estado actual de la pelota.

---

### `Period`

Representa el cuarto del partido que se está disputando actualmente.

Valores posibles:

```python
Period.FIRST_QUARTER
Period.SECOND_QUARTER
Period.THIRD_QUARTER
Period.FOURTH_QUARTER
```

Este tipo se utiliza únicamente como valor devuelto por `current_period()`

## 4. Match constants

### `FIELD_WIDTH`

```python
FIELD_WIDTH: float
```

**Descripción:**  
Ancho de la cancha.

---

### `FIELD_HEIGHT`

```python
FIELD_HEIGHT: float
```

**Descripción:**  
Alto de la cancha.

---

## 5. Match state primitives

Estas primitivas permiten consultar el estado actual del partido. No modifican el estado.

### `self()`

```python
self() -> PlayerState
```

**Descripción:**  
Devuelve una tupla con el identificador y la posición actual del jugador BOT que está ejecutando el comportamiento.


Ejemplo:

```python
my_id, my_position = self()
```

---

### `teammates()`

```python
teammates() -> list[PlayerState]
```

**Descripción:**  
Devuelve una lista de tuplas con el identificador y la posición actual de todos los jugadores BOT compañeros de equipo.

Ejemplo:

```python
for player_id, player_position in teammates():
    # usar player_id y player_position
    ...
```

---

### `opponents()`

```python
opponents() -> list[PlayerState]
```

**Descripción:**  
Devuelve una lista con el identificador y la posición actual de todos los jugadores BOT rivales.

Ejemplo:

```python
for player_id, player_position in opponents():
    # usar player_id y player_position
    ...
```

---

### `ball()`

```python
ball() -> BallState
```

**Descripción:**  
Devuelve la posición y la velocidad actuales de la pelota.

Ejemplo:

```python
ball_position, ball_velocity = ball()
```

---

### `score()`

```python
score() -> tuple[int, int]
```

**Descripción:**  
Devuelve el resultado actual del partido en el formato:

```python
(my_team_score, opponent_score)
```

---

### `match_time_remaining()`

```python
match_time_remaining() -> float
```

**Descripción:**  
Devuelve, en segundos, el tiempo restante del partido.

---

### `current_period()`

```python
current_period() -> Period
```

**Descripción:**  
Devuelve el cuarto del partido que se está disputando actualmente.

---

### `period_time_remaining()`

```python
period_time_remaining() -> float
```

**Descripción:**  
Devuelve, en segundos, el tiempo restante del período actual.

---

### `starting_position()`

```python
starting_position() -> Position
```

**Descripción:**  
Devuelve la posición inicial asignada al jugador BOT en la alineación.

---

### `own_goal()`

```python
own_goal() -> Position
```

**Descripción:**  
Devuelve la posición correspondiente al punto medio del arco propio según el lado actual del jugador.

---

### `opponent_goal()`

```python
opponent_goal() -> Position
```

**Descripción:**  
Devuelve la posición correspondiente al punto medio del arco rival según el lado actual del jugador.

---

## 6. Player capability primitives

Estas primitivas permiten consultar capacidades concretas del jugador BOT que está ejecutando el comportamiento. No modifican el estado.

### `can_kick()`

```python
can_kick() -> bool
```

**Descripción:**  
Indica si el jugador BOT puede intentar patear la pelota en el tic actual.

Para que devuelva `True`, la pelota debe encontrarse dentro del `control_range()` y `tics_until_kick()` debe devolver `0`.

Que `can_kick()` devuelva `True` no garantiza el resultado de la acción. El servidor determina el resultado definitivo teniendo en cuenta el estado actual y las acciones  de los demás jugadores BOT.

---

### `tics_until_kick()`

```python
tics_until_kick() -> int
```

**Descripción:**  
Devuelve la cantidad de tics que faltan para que el jugador BOT pueda volver a patear. 

Este valor está determinado por la estadística `AGILITY`. Mientras mayor sea esta estadística en el jugador BOT, menos tics deberá esperar para volver a patear.

Devuelve `0` si ya está habilitado para hacerlo.

---

### `control_range()`

```python
control_range() -> float
```

**Descripción:**  
Devuelve la distancia máxima a la que puede encontrarse la pelota respecto del jugador BOT para que este pueda interactuar con ella.

Este valor depende de la estadística `CONTROL`.

---

### `can_move_distance(distance)`

```python
can_move_distance(distance: float) -> bool
```

**Descripción:**
Indica si el jugador BOT puede recorrer completamente `distance` durante el próximo tic, teniendo en cuenta su estadística `SPEED` y las reglas de movimiento del servidor.

**Parameters:**
- `distance`: distancia que se desea recorrer.

**Returns:**
- `bool`: `True` si el jugador BOT puede recorrer la distancia durante el proximo tic. `False` si no puede recorrerla.

---

### `speed_for_distance(distance)`

```python
speed_for_distance(distance: float) -> float
```

**Descripción:**  
Devuelve el factor de velocidad necesario para que el jugador BOT recorra `distance` durante el próximo tic. El cálculo tiene en cuenta la estadística `SPEED` del jugador BOT y las reglas de movimiento del servidor.

El valor retornado pertenece al intervalo `[0.0, 1.0]`, donde:
- `0.0` representa no utilizar velocidad de movimiento
- `1.0` representa utilizar la máxima velocidad disponible para el jugador BOT según su estadística `SPEED`.

Si la distancia no puede recorrerse completamente durante el próximo tic, devuelve `1.0`.

**Parameters:**
- `distance`: distancia que se desea recorrer.

**Returns:**
- `float`: factor de velocidad necesario para recorrer la distancia indicada durante el próximo tic. Valor perteneciente al intervalo `[0.0, 1.0]`.

---

### `can_kick_distance(direction, distance)`

```python
can_kick_distance(direction: Direction, distance: float) -> bool
```

**Descripción:**
Indica si un único pateo del jugador BOT en `direction` puede hacer que la pelota recorra `distance`, teniendo en cuenta su estadística `POWER`, la velocidad actual de la pelota y las reglas físicas definidas en el servidor.

**Parameters:**
- `direction`: dirección en la que se desea patear la pelota
- `distance`: distancia que se desea que recorra la pelota.

**Returns:**
`bool`: `True` si la pelota puede alcanzar la distancia indicada con un único pateo en la dirección especificada. `False` si no puede alcanzarla.

---

### `kick_force_for_distance(direction, distance)`

```python
kick_force_for_distance(direction: Direction, distance: float) -> float
```

**Descripción:**  
Devuelve el factor de fuerza necesario para que un jugador BOT patee la pelota en `direction` y esta recorra aproximadamente `distance`.

El cálculo tiene en cuenta la estadística `POWER` del jugador BOT, la velocidad actual de la pelota, la dirección de pateo y las reglas físicas definidas por el servidor. Por lo tanto, el factor necesario para alcanzar una misma distancia puede variar según la velocidad y dirección que tenga la pelota al momento de patear.

El valor retornado pertenece al intervalo `[0.0, 1.0]`, donde:
- `0.0` representa no aplicar ninguna fuerza sobre la pelota
- `1.0` representa utilizar la máxima fuerza de pateo del jugador BOT según su estadística `POWER`.

Si la distancia requerida no puede alcanzarse utilizando la máxima fuerza disponible, devuelve `1.0`.

Una vez realizada la acción de patear, la pelota continúa desplazándose de acuerdo con su velocidad resultante y las reglas físicas del servidor.

**Parameters:**
- `direction`: dirección en la que se desea patear la pelota.
- `distance`: distancia que se desea que recorra la pelota.

**Returns:**
- `float`: factor de fuerza necesario para que la pelota alcance aproximadamente la distancia indicada en la dirección especificada. Valor perteneciente al intervalo `[0.0, 1.0]`.

---

## 7. Actions primitives

Estas son las únicas primitivas que puede devolver `play()`. 

Cada ejecución de `play()` debe devolver exactamente una de ellas.

Pueden modificar el estado.


### `move(direction, speed_factor)`

```python
move(
    direction: Direction,
    speed_factor: float
)
```

**Descripción:**  
Solicita que el jugador BOT se mueva en `direction` durante el próximo tic utilizando una fracción de su capacidad máxima de movimiento.

El parámetro `speed_factor` debe pertenecer al intervalo `[0.0, 1.0]`. El valor `1.0` indica que el jugador BOT debe utilizar su máxima velocidad disponible, determinada por su estadística `SPEED`.

**Parameters:**
- `direction`: dirección en la que debe desplazarse el jugador. Valor de tipo `Direction`.
- `speed_factor`: fracción de la velocidad máxima que se desea utilizar, entre `0.0` y `1.0`.

**State effect:**  
Puede modificar la posición del jugador en el siguiente estado de la partida.

---

### `kick(direction, force_factor)`

```python
kick(
    direction: Direction,
    force_factor: float
)
```

**Descripción:**  
Solicita que el jugador BOT intente patear la pelota en `direction` utilizando una fracción de su fuerza.

El parámetro `force_factor` debe pertenecer al intervalo `[0.0, 1.0]`. El valor `1.0` representa utilizar la máxima fuerza disponible, determinada por la estadística `POWER`.

**Parameters:**
- `direction`: dirección en la que se desea impulsar la pelota. Valor de tipo `Direction`.
- `force_factor`: fracción de la fuerza máxima del jugador BOT que se desea utilizar, entre `0.0` y `1.0`.

**State effect:**  
Si la acción es válida, puede modificar la velocidad de la pelota en el siguiente estado de la partida.

Si la pelota ya se encuentra en movimiento, el servidor tendrá en cuenta la velocidad actual para calcular la velocidad resultante luego de que el jugador BOT patee.

El servidor determina el resultado definitivo de la acción teniendo en cuenta el estado actual del partido y las acciones de los demás jugadores BOT.

---

### `wait()`

```python
wait()
```

**Descripción:**  
Indica que el jugador BOT no realizará ninguna acción voluntaria durante el próximo tic.

**State effect:**  
No produce modificaciones voluntarias sobre el estado.

---

## 8. Geometry and physics helpers

Estas funciones facilitan cálculos frecuentes para definir comportamientos. No modifican el estado de la partida.

### `distance(from_position, to_position)`

```python
distance(
    from_position: Position,
    to_position: Position
) -> float
```

**Descripción:**  
Devuelve la distancia entre dos posiciones.

**Parameters:**
- `from_position`: posición de origen.
- `to_position`: posición de destino.

**Returns:**
- `float`: distancia entre ambas posiciones.

---

### `direction_to(from_position, to_position)`

```python
direction_to(
    from_position: Position,
    to_position: Position
) -> Direction
```

**Descripción:**  
Devuelve una dirección unitaria desde `from_position` hacia `to_position`.

**Parameters:**
- `from_position`: posición de origen.
- `to_position`: posición de destino.

**Returns:**
- `Direction`: dirección desde el origen hacia el destino.

---

### `next_ball_position()`

```python
next_ball_position() -> Position
```

**Descripción:**  
Devuelve la posición estimada de la pelota en el próximo tic a partir de su posición, velocidad actuales y reglas físicas definidas en el servidor.

La estimación contempla posibles rebotes contra los límites de la cancha, pero no considera posibles interacciones de otros jugadores BOT durante el tic actual.

**Returns:**
- `Position`: posición estimada de la pelota en el próximo tic.

---

## 9. Complete behavior example

```python
def play():
    _, my_position = self()
    ball_position, _ = ball()

    ball_distance = distance(my_position, ball_position)

    # Pelota dentro del rango de control
    if ball_distance <= control_range():

        if can_kick():
            goal = opponent_goal()
            goal_distance = distance(ball_position, goal)
            goal_direction = direction_to(ball_position, goal)

            # Patea si el arco está al alcance
            if can_kick_distance(goal_direction, goal_distance):
                return kick(
                    goal_direction,
                    1.0
                )

            # Si no puede patear al arco, busca al compañero más cercano al que
            # pueda hacer llegar la pelota
            closest_teammate = None
            closest_distance = None

            for _, teammate_position in teammates():
                teammate_distance = distance(
                    ball_position,
                    teammate_position
                )
                teammate_direction = direction_to(
                    ball_position,
                    teammate_position
                )

                if can_kick_distance(teammate_direction, teammate_distance):
                    if (
                        closest_distance is None
                        or teammate_distance < closest_distance
                    ):
                        closest_teammate = teammate_position
                        closest_distance = teammate_distance

            if closest_teammate is not None:
                pass_direction = direction_to(ball_position, closest_teammate)
                return kick(
                    pass_direction,
                    kick_force_for_distance(pass_direction, closest_distance)
                )

            # Si no llega a pasar la pelota, espera
            return wait()

        # La pelota está dentro del rango de control, pero el jugador BOT
        # todavía está en cooldown de pateo. Acompaña la trayectoria de la pelota.
        target = next_ball_position()
        move_distance = distance(my_position, target)

        return move(
            direction_to(my_position, target),
            speed_for_distance(move_distance)
        )

    # Intenta quedar dentro del rango de control de la pelota en el próximo tic
    target = next_ball_position()
    target_distance = distance(my_position, target)

    required_distance = max(
        0.0,
        target_distance - control_range()
    )

    if required_distance == 0.0:
        return wait()

    if can_move_distance(required_distance):
        return move(
            direction_to(my_position, target),
            speed_for_distance(required_distance)
        )

    # Si no puede entrar en rango de control en el siguiente tic
    # Buscar rival cercano alcanzable en el próximo tic
    closest_opponent = None
    closest_distance = None

    for _, opponent_position in opponents():
        opponent_distance = distance(
            my_position,
            opponent_position
        )

        if can_move_distance(opponent_distance):
            if (
                closest_distance is None
                or opponent_distance < closest_distance
            ):
                closest_opponent = opponent_position
                closest_distance = opponent_distance

    if closest_opponent is not None:
        return move(
            direction_to(my_position, closest_opponent),
            speed_for_distance(closest_distance)
        )

    # Si no hay rival cercano alcanzable en el proximo tic
    # Volver a la posición inicial
    initial_position = starting_position()
    initial_distance = distance(my_position, initial_position)

    if initial_distance > 0:
        return move(
            direction_to(my_position, initial_position),
            speed_for_distance(initial_distance)
        )

    return wait()
```

---

## 10. Execution rules

- `play()` se ejecuta una vez por tic para cada jugador BOT que tenga asignado el comportamiento.
- En cada ejecución, `play()` debe devolver exactamente una de las primitivas de acción válidas: `move(...)`, `kick(...)` o `wait()`.
- Cada jugador BOT evalúa su comportamiento utilizando el estado actual de la partida correspondiente al mismo tic.
- Las primitivas de consulta y las funciones auxiliares no modifican el estado de la partida. Las primitivas de acción representan una solicitud de acción para el tic actual. El servidor es el responsable de resolverlas y calcular el siguiente estado de la partida.
- Las acciones no persisten entre tics. En cada nuevo tic, `play()` se ejecuta nuevamente y debe devolver una nueva acción.
- Un mismo comportamiento puede ser asignado a distintos jugadores BOT. Las primitivas relativas al jugador BOT actual utilizan automáticamente el estado y las capacidades del jugador que está ejecutando el comportamiento.
- Cada ejecución de `play()` debe finalizar dentro del límite de tiempo establecido por el servidor. Si supera dicho límite, no finaliza correctamente o devuelve un valor distinto de una acción válida, la ejecución se considera inválida para ese tic.
- El usuario debe evitar operaciones cuyo tiempo de ejecución no esté acotado, como bucles infinitos o cálculos excesivamente costosos.

---

## 11. Coach (DT) behaviors

### 11.1 Overview

Además de los comportamientos de jugador, cada club puede definir comportamientos DT (director técnico).

Un comportamiento DT no controla a un jugador BOT. Su función es cambiar la estrategia del equipo durante el partido sin que el usuario tenga que intervenir: cuando ocurre un gol o empieza un período, el DT analiza el partido y decide qué comportamiento pasa a ejecutar cada uno de sus jugadores BOT en cancha. También puede pedir una sustitución, que se ejecuta en la pausa siguiente.

Para usar un DT:

1. Se crea el comportamiento DT, con un nombre y su código. El nombre no puede estar repetido entre los DT del club ni coincidir con el de un comportamiento default.
2. Se asigna en la plantilla del partido. Asignar un DT es opcional: si la plantilla no tiene uno, el equipo juega sin DT.

Los comportamientos DT no pueden crearse ni eliminarse mientras el usuario está jugando un partido.

---

### 11.2 Coach entry point

Todo comportamiento DT debe definir obligatoriamente la función:

```python
def coach():
    ...
```

Si el código no define `coach()`, el comportamiento DT no puede crearse.

Fuera de las funciones solo se permiten definiciones de funciones y constantes: el código no puede ejecutar instrucciones al cargarse. Tampoco se permiten `import`, clases, funciones `async`, generadores (`yield`), el acceso a atributos que empiezan con `__` ni las funciones `open`, `eval`, `exec`, `compile`, `getattr`, `setattr`, `delattr`, `globals`, `locals`, `vars`, `input`, `breakpoint` y `__import__`. Si el código no cumple estas reglas, el comportamiento DT no puede crearse.

Al crearse, el código pasa por la misma validación que los comportamientos de jugador, adaptada al DT:

- `coach()` no puede llevar parámetros obligatorios y debe tener al menos un `return` con valor.
- Solo puede usar las primitivas del DT (11.4 a 11.6), las funciones y variables definidas en el propio código y builtins seguros (`len`, `range`, `min`, `max`, `sorted`, etc.). Las primitivas exclusivas de jugador, como `move()`, `kick()`, `wait()` o `self()`, no están disponibles.
- `coach()` se ejecuta de prueba, en un proceso aislado y con un límite de tiempo, en escenarios de ejemplo que cubren los tres disparadores y los casos en que se puede y no se puede sustituir. En cada uno debe terminar sin errores y devolver una lista, posiblemente vacía, cuyos elementos estén construidos con `assign(...)` o `substitute(...)`.

La prueba no garantiza que el DT funcione en cualquier partido: un código que solo falla en situaciones que no aparecen en los escenarios de ejemplo pasa la validación. Durante el partido, si `coach()` falla, no se aplica ningún cambio (ver 11.8). Si la validación falla, la respuesta indica el motivo.

### `coach()`

**Descripción:**
Es el punto de entrada del comportamiento DT. El servidor la ejecuta cada vez que ocurre un gol o empieza un período (ver 11.8).

La función debe devolver una lista de asignaciones construidas con `assign(...)` y de sustituciones construidas con `substitute(...)`. La lista puede estar vacía, lo que indica que el DT no realiza cambios.

```python
[assign(...), assign(...), ...]
[assign(...), substitute(...)]
[]
```

Cualquier otro valor de retorno se considera inválido.

### Valid example

```python
def coach():
    my_score, opponent_score = score()

    if my_score < opponent_score:
        return [
            assign(player_id, "Attacker")
            for player_id, _ in teammates()
        ]

    return []
```

### Invalid example

```python
def coach():
    return move((1.0, 0.0), 1.0)
```

`move(...)` es una acción de jugador y no una acción válida para un comportamiento DT.

---

### 11.3 Coach data types

### `Assignment`

```python
Assignment = tuple[int, str]
```

Representa un cambio de comportamiento solicitado por el DT.

- Primer componente: identificador del jugador BOT propio en cancha.
- Segunda componente: nombre del comportamiento de jugador que se le desea asignar.

Se obtiene mediante la acción `assign(...)`.

---

### `Substitution`

Representa una sustitución solicitada por el DT: el jugador BOT que sale y el suplente que entra.

Se obtiene mediante la acción `substitute(...)`.

---

### `CoachTrigger`

Representa el evento que provocó la ejecución del DT.

Valores posibles:

```python
CoachTrigger.GOAL_FOR       # gol del propio equipo
CoachTrigger.GOAL_AGAINST   # gol del equipo rival
CoachTrigger.PERIOD_START   # inicio de un período
```

Este tipo se utiliza únicamente como valor devuelto por `trigger()`.

---

### 11.4 Available primitives

Un comportamiento DT puede utilizar las siguientes primitivas de consulta de la sección 5, con el mismo significado:

- `score()`
- `match_time_remaining()`
- `current_period()`
- `period_time_remaining()`
- `teammates()`: devuelve todos los jugadores BOT propios en cancha.
- `opponents()`
- `ball()`

También puede utilizar las funciones auxiliares `distance(...)` y `direction_to(...)` de la sección 8, y las constantes de la sección 4.

Las primitivas que se refieren a un jugador BOT concreto (`self()`, `starting_position()`, `own_goal()`, `opponent_goal()`, las de la sección 6 y `next_ball_position()`) no están disponibles para un DT. Las acciones `move(...)`, `kick(...)` y `wait()` tampoco.

---

### 11.5 Coach primitives

Estas primitivas solo pueden utilizarse dentro de un comportamiento DT. No modifican el estado.

### `trigger()`

```python
trigger() -> CoachTrigger
```

**Descripción:**
Devuelve el evento que provocó la ejecución actual del DT.

Ejemplo:

```python
if trigger() == CoachTrigger.GOAL_AGAINST:
    ...
```

---

### `current_behavior(player_id)`

```python
current_behavior(player_id: int) -> str | None
```

**Descripción:**
Devuelve el nombre del comportamiento que está ejecutando actualmente el jugador BOT propio indicado.

**Parameters:**
- `player_id`: identificador de un jugador BOT propio en cancha.

**Returns:**
- `str`: nombre del comportamiento que está ejecutando el jugador.
- `None`: si el jugador no es propio o no está en cancha.

---

### `available_behaviors()`

```python
available_behaviors() -> list[str]
```

**Descripción:**
Devuelve los nombres de los comportamientos que el DT puede asignar: los comportamientos de jugador del club y los comportamientos default.

---

### `bench()`

```python
bench() -> list[int]
```

**Descripción:**
Devuelve los identificadores de los suplentes del club.

---

### `can_substitute()`

```python
can_substitute() -> bool
```

**Descripción:**
Devuelve `True` si en este momento se aceptaría una sustitución pedida por el DT. Devuelve `False` si:
- ya se ejecutó la sustitución de este período;
- el partido está en el último cuarto o la ventana de sustituciones está cerrada;
- el usuario ya pidió una sustitución manual que todavía no se ejecutó.

---

### 11.6 Coach actions

### `assign(player_id, behavior_name)`

```python
assign(
    player_id: int,
    behavior_name: str
) -> Assignment
```

**Descripción:**
Solicita que el jugador BOT `player_id` pase a ejecutar el comportamiento `behavior_name`.

**Parameters:**
- `player_id`: identificador de un jugador BOT propio en cancha.
- `behavior_name`: uno de los nombres devueltos por `available_behaviors()`.

**State effect:**
Si la asignación es válida, el jugador BOT ejecuta el nuevo comportamiento a partir del tic siguiente.

Una asignación se descarta, sin afectar al resto de la lista, si:
- `player_id` corresponde a un jugador rival, a un suplente o a un jugador inexistente;
- `behavior_name` no es uno de los nombres devueltos por `available_behaviors()`.

---

### `substitute(player_out_id, player_in_id)`

```python
substitute(
    player_out_id: int,
    player_in_id: int
) -> Substitution
```

**Descripción:**
Solicita que el jugador BOT `player_out_id` sea reemplazado por el suplente `player_in_id`.

**Parameters:**
- `player_out_id`: identificador de un jugador BOT propio en cancha.
- `player_in_id`: uno de los identificadores devueltos por `bench()`.

**State effect:**
Si el pedido es válido, la sustitución se ejecuta en la pausa siguiente. El jugador que entra hereda el comportamiento y la posición inicial del que sale.

Un pedido se descarta, sin afectar al resto de la lista, si:
- `player_out_id` no es un jugador propio en cancha;
- `player_in_id` no es un suplente propio;
- `can_substitute()` devuelve `False`.

```python
def coach():
    if trigger() == CoachTrigger.PERIOD_START and can_substitute():
        on_field = teammates()
        substitutes = bench()

        if on_field and substitutes:
            return [substitute(on_field[0][0], substitutes[0])]

    return []
```

---

### 11.7 Complete coach example

```python
def coach():
    my_score, opponent_score = score()
    assignments = []

    # Si vamos perdiendo en el último cuarto, todos atacan
    if (
        current_period() == Period.FOURTH_QUARTER
        and my_score < opponent_score
    ):
        for player_id, _ in teammates():
            if current_behavior(player_id) != "Attacker":
                assignments.append(assign(player_id, "Attacker"))

        return assignments

    # Si acabamos de hacer un gol y vamos ganando, los dos jugadores
    # más alejados de la pelota pasan a defender
    if (
        trigger() == CoachTrigger.GOAL_FOR
        and my_score > opponent_score
    ):
        ball_position, _ = ball()

        by_distance = sorted(
            (distance(player_position, ball_position), player_id)
            for player_id, player_position in teammates()
        )

        for _, player_id in by_distance[-2:]:
            assignments.append(assign(player_id, "Defender"))

    return assignments
```

---

### 11.8 Coach execution rules

- `coach()` se ejecuta únicamente cuando:
  - cualquiera de los dos equipos hace un gol;
  - empieza un período.

  En el resto de los tics, el DT no se ejecuta.
- Cuando ocurre uno de estos eventos, se ejecuta el DT de cada equipo que tenga uno asignado.
- Los cambios de comportamiento rigen a partir del tic siguiente.
- Las asignaciones inválidas se descartan una por una; las válidas de la misma lista se aplican igual. Esto incluye los elementos de la lista que no son asignaciones construidas con `assign(...)`.
- Si una misma lista contiene más de una asignación para el mismo jugador BOT, se aplica la última.
- Si en el mismo tic el usuario cambia manualmente el comportamiento de un jugador BOT y el DT también le asigna uno, se aplica el cambio manual.
- El estado del partido (`current_behavior_id` y `current_behavior_name`) refleja el cambio a partir del tic en que se aplica, sea manual o del DT, no en el momento del pedido.
- Cada ejecución de `coach()` debe finalizar dentro del límite de tiempo establecido por el servidor. Si lanza un error, supera ese límite o devuelve algo que no es una lista, no se aplica ningún cambio: los jugadores BOT siguen con sus comportamientos y el partido continúa.
- El usuario debe evitar operaciones cuyo tiempo de ejecución no esté acotado, como bucles infinitos o cálculos excesivamente costosos.
- Las sustituciones pedidas por el DT comparten el límite con las manuales: una por período, y ninguna en el último cuarto.
- Una sustitución pedida por el DT se ejecuta en la pausa siguiente, no en el tic siguiente. Hasta entonces, el jugador que entra sigue en el banco: una asignación a ese jugador en la misma lista se descarta. Para cambiarle el comportamiento, el DT puede asignárselo cuando empiece el período siguiente.
- Si una misma lista contiene más de una sustitución válida, se aplica la última. Lo mismo ocurre entre ejecuciones del DT dentro de un período: un pedido nuevo reemplaza al anterior hasta que se ejecute.
- Si el usuario pide una sustitución manual, esta reemplaza a la pedida por el DT. Si ya hay una sustitución manual pendiente, el pedido del DT se descarta.
