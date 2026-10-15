"""SCRUM-101 update default behaviors

Revision ID: a1f3856ba12c
Revises: 40374f37fd39
Create Date: 2026-10-14 23:53:09.173680

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f3856ba12c'
down_revision: Union[str, Sequence[str], None] = '40374f37fd39'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_ATTACKER_CODE = """
# Zona ofensiva del delantero, expresada como porcentaje
# del recorrido entre el arco propio y el rival.
ZONE_START = 0.6
ZONE_END = 1.0

# Distancia máxima a la pelota para considerar que
# un compañero está mejor posicionado para disputarla.
TEAMMATE_BALL_DISTANCE = 2.0

# Distancia utilizada para buscar espacios hacia los costados.
UNMARK_DISTANCE = 3.0


def zone_limits():
    own = own_goal()
    opponent = opponent_goal()

    start_x = own[0] + (opponent[0] - own[0]) * ZONE_START
    end_x = own[0] + (opponent[0] - own[0]) * ZONE_END

    return min(start_x, end_x), max(start_x, end_x)


def ball_in_zone(ball_position):
    min_x, max_x = zone_limits()
    return min_x <= ball_position[0] <= max_x


def attacking_position():
    own = own_goal()
    opponent = opponent_goal()
    _, start_y = starting_position()

    # Posición base del delantero en el 75% del campo.
    return (
        own[0] + (opponent[0] - own[0]) * 0.75,
        start_y,
    )


def teammate_better_positioned(ball_position, my_distance):
    # Evita que varios compañeros persigan la misma pelota.
    for _, teammate_position in teammates():
        teammate_distance = distance(
            teammate_position,
            ball_position,
        )

        if (
            teammate_distance <= TEAMMATE_BALL_DISTANCE
            and teammate_distance < my_distance
        ):
            return True

    return False


def unmarked_position():
    base = attacking_position()

    # Prueba dos posibles posiciones de desmarque:
    # una por encima y otra por debajo de su posición base.
    upper = (
        base[0],
        base[1] - UNMARK_DISTANCE,
    )

    lower = (
        base[0],
        base[1] + UNMARK_DISTANCE,
    )

    upper_distance = None
    lower_distance = None

    # Para cada posición candidata se busca la distancia
    # al rival más cercano.
    for _, opponent_position in opponents():
        distance_to_upper = distance(
            upper,
            opponent_position,
        )

        distance_to_lower = distance(
            lower,
            opponent_position,
        )

        if (
            upper_distance is None
            or distance_to_upper < upper_distance
        ):
            upper_distance = distance_to_upper

        if (
            lower_distance is None
            or distance_to_lower < lower_distance
        ):
            lower_distance = distance_to_lower

    # Elige la posición cuyo rival más cercano esté más lejos.
    if upper_distance >= lower_distance:
        return upper

    return lower


def move_to(my_position, target):
    target_distance = distance(my_position, target)

    if target_distance == 0:
        return wait()

    return move(
        direction_to(my_position, target),
        speed_for_distance(target_distance),
    )


def play():
    _, my_position = self()
    ball_position, _ = ball()

    ball_distance = distance(
        my_position,
        ball_position,
    )

    # Si la pelota está dentro de su zona ofensiva,
    # el delantero intenta participar directamente.
    if ball_in_zone(ball_position):

        # Si tiene la pelota dentro de su rango de control,
        # intenta patear al arco.
        if ball_distance <= control_range():
            if not can_kick():
                return wait()

            goal = opponent_goal()

            # El delantero remata utilizando toda su potencia disponible.
            return kick(
                direction_to(
                    ball_position,
                    goal,
                ),
                1.0,
            )

        # Si ningún compañero está mejor posicionado,
        # persigue la pelota.
        if not teammate_better_positioned(
            ball_position,
            ball_distance,
        ):
            return move_to(
                my_position,
                ball_position,
            )

    # Si la pelota está fuera de su zona, busca desmarcarse.
    return move_to(
        my_position,
        unmarked_position(),
    )
"""


NEW_DEFENDER_CODE = """
# Zona defensiva del jugador.
ZONE_START = 0.0
ZONE_END = 0.4

TEAMMATE_BALL_DISTANCE = 2.0

# Distancia que intenta mantener respecto del rival marcado.
MARKING_DISTANCE = 1.0


def zone_limits():
    own = own_goal()
    opponent = opponent_goal()

    start_x = own[0] + (opponent[0] - own[0]) * ZONE_START
    end_x = own[0] + (opponent[0] - own[0]) * ZONE_END

    return min(start_x, end_x), max(start_x, end_x)


def ball_in_zone(ball_position):
    min_x, max_x = zone_limits()
    return min_x <= ball_position[0] <= max_x


def position_in_zone(position):
    min_x, max_x = zone_limits()
    return min_x <= position[0] <= max_x


def clamp_to_zone(position):
    min_x, max_x = zone_limits()

    # Impide que una posición objetivo saque al defensor
    # fuera de su zona asignada.
    return (
        min(max(position[0], min_x), max_x),
        position[1],
    )


def position_near_ball_in_zone(ball_position):
    min_x, max_x = zone_limits()

    # Sigue horizontalmente la jugada, pero sin abandonar
    # los límites de su zona defensiva.
    target_x = min(
        max(ball_position[0], min_x),
        max_x,
    )

    _, start_y = starting_position()

    return (target_x, start_y)


def teammate_better_positioned(ball_position, my_distance):
    # Si un compañero ya está suficientemente cerca
    # y además está más cerca que este jugador,
    # el defensor evita perseguir también la pelota.
    for _, teammate_position in teammates():
        teammate_distance = distance(
            teammate_position,
            ball_position,
        )

        if (
            teammate_distance <= TEAMMATE_BALL_DISTANCE
            and teammate_distance < my_distance
        ):
            return True

    return False


def most_advanced_teammate():
    goal = opponent_goal()

    best_position = None
    best_distance = None

    # Busca al compañero más cercano al arco rival
    # para intentar un pase que haga avanzar la jugada.
    for _, teammate_position in teammates():
        goal_distance = distance(
            teammate_position,
            goal,
        )

        if (
            best_distance is None
            or goal_distance < best_distance
        ):
            best_position = teammate_position
            best_distance = goal_distance

    return best_position


def opponent_to_mark():
    goal = own_goal()

    best_position = None
    best_distance = None

    # Solo considera rivales dentro de la zona defensiva.
    # Entre ellos elige al más cercano al arco propio.
    for _, opponent_position in opponents():
        if not position_in_zone(opponent_position):
            continue

        goal_distance = distance(
            opponent_position,
            goal,
        )

        if (
            best_distance is None
            or goal_distance < best_distance
        ):
            best_position = opponent_position
            best_distance = goal_distance

    return best_position


def marking_position(opponent_position):
    goal = own_goal()

    # Se posiciona entre el rival y el arco propio.
    direction = direction_to(
        opponent_position,
        goal,
    )

    target = (
        opponent_position[0] + direction[0] * MARKING_DISTANCE,
        opponent_position[1] + direction[1] * MARKING_DISTANCE,
    )

    return clamp_to_zone(target)


def move_to(my_position, target):
    target_distance = distance(my_position, target)

    if target_distance == 0:
        return wait()

    return move(
        direction_to(my_position, target),
        speed_for_distance(target_distance),
    )


def play():
    _, my_position = self()
    ball_position, _ = ball()

    ball_distance = distance(
        my_position,
        ball_position,
    )

    # Si la pelota entra en su zona defensiva,
    # intenta recuperarla.
    if ball_in_zone(ball_position):

        # Si consigue controlarla, busca al compañero
        # más adelantado para realizar un pase.
        if ball_distance <= control_range():
            if not can_kick():
                return wait()

            teammate_position = most_advanced_teammate()

            if teammate_position is None:
                return wait()

            pass_direction = direction_to(
                ball_position,
                teammate_position,
            )

            pass_distance = distance(
                ball_position,
                teammate_position,
            )

            return kick(
                pass_direction,
                kick_force_for_distance(
                    pass_direction,
                    pass_distance,
                ),
            )

        # Evita ir a disputar la pelota si un compañero
        # ya está más cerca y bien posicionado.
        if not teammate_better_positioned(
            ball_position,
            ball_distance,
        ):
            return move_to(
                my_position,
                ball_position,
            )

    # Cuando la pelota está fuera de su zona,
    # intenta marcar al rival más peligroso.
    opponent_position = opponent_to_mark()

    if opponent_position is not None:
        return move_to(
            my_position,
            marking_position(opponent_position),
        )

    # Si no hay rivales para marcar, acompaña la jugada
    # manteniéndose dentro de su zona defensiva.
    return move_to(
        my_position,
        position_near_ball_in_zone(ball_position),
    )
"""


NEW_MIDFIELDER_CODE = """
# Zona central del mediocampista.
# Se superpone parcialmente con las zonas
# del defensor y del delantero.
ZONE_START = 0.3
ZONE_END = 0.7

TEAMMATE_BALL_DISTANCE = 2.0


def zone_limits():
    own = own_goal()
    opponent = opponent_goal()

    start_x = own[0] + (opponent[0] - own[0]) * ZONE_START
    end_x = own[0] + (opponent[0] - own[0]) * ZONE_END

    return min(start_x, end_x), max(start_x, end_x)


def ball_in_zone(ball_position):
    min_x, max_x = zone_limits()
    return min_x <= ball_position[0] <= max_x


def position_near_ball_in_zone(ball_position):
    min_x, max_x = zone_limits()

    # Acompaña horizontalmente la posición de la pelota,
    # pero nunca sale de su zona central.
    target_x = min(
        max(ball_position[0], min_x),
        max_x,
    )

    _, start_y = starting_position()

    return (target_x, start_y)


def teammate_better_positioned(ball_position, my_distance):
    # Evita que varios jugadores persigan la pelota
    # cuando un compañero ya está más cerca.
    for _, teammate_position in teammates():
        teammate_distance = distance(
            teammate_position,
            ball_position,
        )

        if (
            teammate_distance <= TEAMMATE_BALL_DISTANCE
            and teammate_distance < my_distance
        ):
            return True

    return False


def closest_teammate(ball_position):
    closest_position = None
    closest_distance = None

    # Busca al compañero más cercano a la pelota
    # para realizar un pase corto y simple.
    for _, teammate_position in teammates():
        teammate_distance = distance(
            ball_position,
            teammate_position,
        )

        if (
            closest_distance is None
            or teammate_distance < closest_distance
        ):
            closest_position = teammate_position
            closest_distance = teammate_distance

    return closest_position, closest_distance


def move_to(my_position, target):
    target_distance = distance(my_position, target)

    if target_distance == 0:
        return wait()

    return move(
        direction_to(my_position, target),
        speed_for_distance(target_distance),
    )


def play():
    _, my_position = self()
    ball_position, _ = ball()

    ball_distance = distance(
        my_position,
        ball_position,
    )

    # Si la pelota está dentro de la zona central,
    # el mediocampista intenta participar de la jugada.
    if ball_in_zone(ball_position):

        # Si tiene la pelota bajo control, busca al
        # compañero más cercano para continuar la jugada.
        if ball_distance <= control_range():
            if not can_kick():
                return wait()

            teammate_position, teammate_distance = closest_teammate(
                ball_position
            )

            if teammate_position is None:
                return wait()

            pass_direction = direction_to(
                ball_position,
                teammate_position,
            )

            return kick(
                pass_direction,
                kick_force_for_distance(
                    pass_direction,
                    teammate_distance,
                ),
            )

        # Solo persigue la pelota si ningún compañero
        # está ya mejor posicionado para disputarla.
        if not teammate_better_positioned(
            ball_position,
            ball_distance,
        ):
            return move_to(
                my_position,
                ball_position,
            )

    # Si la pelota está fuera de su zona,
    # acompaña la jugada desde el punto más cercano posible.
    return move_to(
        my_position,
        position_near_ball_in_zone(ball_position),
    )
"""


# Estado anterior a SCRUM-101.
# Attacker proviene del seed original 017bba20c37f.
OLD_ATTACKER_CODE = """
def is_ball_in_opponent_half(ball_position):
    return (
        distance(ball_position, opponent_goal())
        < distance(ball_position, own_goal())
    )


def attacking_position():
    own = own_goal()
    opponent = opponent_goal()
    _, start_y = starting_position()

    return (
        own[0] + (opponent[0] - own[0]) * 0.75,
        start_y,
    )


def move_to(my_position, target):
    target_distance = distance(my_position, target)

    if target_distance == 0:
        return wait()

    return move(
        direction_to(my_position, target),
        speed_for_distance(target_distance),
    )


def play():
    _, my_position = self()
    ball_position, _ = ball()

    if not is_ball_in_opponent_half(ball_position):
        return move_to(
            my_position,
            attacking_position(),
        )

    ball_distance = distance(
        my_position,
        ball_position,
    )

    if ball_distance <= control_range():
        if not can_kick():
            return wait()

        goal = opponent_goal()

        goal_direction = direction_to(
            ball_position,
            goal,
        )

        goal_distance = distance(
            ball_position,
            goal,
        )

        return kick(
            goal_direction,
            kick_force_for_distance(
                goal_direction,
                goal_distance,
            )
        )

    return move_to(
        my_position,
        ball_position,
    )
"""


OLD_DEFENDER_CODE = """
def is_ball_in_own_half(ball_position):
    return (
        distance(ball_position, own_goal())
        <= distance(ball_position, opponent_goal())
    )


def defensive_position():
    own = own_goal()
    opponent = opponent_goal()
    _, start_y = starting_position()

    return (
        own[0] + (opponent[0] - own[0]) * 0.25,
        start_y,
    )


def most_advanced_teammate():
    goal = opponent_goal()

    best_position = None
    best_distance = None

    for _, teammate_position in teammates():
        teammate_goal_distance = distance(
            teammate_position,
            goal,
        )

        if (
            best_distance is None
            or teammate_goal_distance < best_distance
        ):
            best_position = teammate_position
            best_distance = teammate_goal_distance

    return best_position


def move_to(my_position, target):
    target_distance = distance(my_position, target)

    if target_distance == 0:
        return wait()

    return move(
        direction_to(my_position, target),
        speed_for_distance(target_distance),
    )


def play():
    _, my_position = self()
    ball_position, _ = ball()

    if not is_ball_in_own_half(ball_position):
        return move_to(
            my_position,
            defensive_position(),
        )

    ball_distance = distance(
        my_position,
        ball_position,
    )

    if ball_distance <= control_range():
        if not can_kick():
            return wait()

        teammate_position = most_advanced_teammate()

        pass_direction = direction_to(
            ball_position,
            teammate_position,
        )

        pass_distance = distance(
            ball_position,
            teammate_position,
        )

        return kick(
            pass_direction,
            kick_force_for_distance(
                pass_direction,
                pass_distance,
            )
        )

    return move_to(
        my_position,
        ball_position,
    )
"""


OLD_MIDFIELDER_CODE = """
def most_advanced_teammate():
    goal = opponent_goal()

    best_position = None
    best_distance = None

    for _, teammate_position in teammates():
        teammate_goal_distance = distance(
            teammate_position,
            goal,
        )

        if (
            best_distance is None
            or teammate_goal_distance < best_distance
        ):
            best_position = teammate_position
            best_distance = teammate_goal_distance

    return best_position


def play():
    _, my_position = self()
    ball_position, _ = ball()

    ball_distance = distance(
        my_position,
        ball_position,
    )

    if ball_distance <= control_range():
        if not can_kick():
            return wait()

        teammate_position = most_advanced_teammate()

        pass_direction = direction_to(
            ball_position,
            teammate_position,
        )

        pass_distance = distance(
            ball_position,
            teammate_position,
        )

        return kick(
            pass_direction,
            kick_force_for_distance(
                pass_direction,
                pass_distance,
            )
        )

    return move(
        direction_to(
            my_position,
            ball_position,
        ),
        speed_for_distance(
            ball_distance,
        ),
    )
"""


def _update_default_behavior(
    name: str,
    code: str,
) -> None:
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            UPDATE behaviors
            SET code = :code
            WHERE name = :name
              AND club_id IS NULL
              AND is_default = TRUE
            """
        ),
        {
            "name": name,
            "code": code,
        },
    )


def upgrade() -> None:
    _update_default_behavior(
        "Attacker",
        NEW_ATTACKER_CODE,
    )

    _update_default_behavior(
        "Midfielder",
        NEW_MIDFIELDER_CODE,
    )

    _update_default_behavior(
        "Defender",
        NEW_DEFENDER_CODE,
    )


def downgrade() -> None:
    _update_default_behavior(
        "Attacker",
        OLD_ATTACKER_CODE,
    )

    _update_default_behavior(
        "Midfielder",
        OLD_MIDFIELDER_CODE,
    )

    _update_default_behavior(
        "Defender",
        OLD_DEFENDER_CODE,
    )