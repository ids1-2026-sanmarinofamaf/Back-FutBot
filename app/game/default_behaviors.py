ATTACKER_NAME = "Attacker"

ATTACKER_CODE = """
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

    if ball_distance > control_range():
        if teammate_near_ball(
            ball_position,
            ball_distance,
        ):
            return move_to(
                my_position,
                attacking_position(),
            )

        return move_to(
            my_position,
            ball_position,
        )

    if not can_kick():
        return wait()

    goal = opponent_goal()

    return kick(
        direction_to(
            ball_position,
            goal,
        ),
        1.0,
    )
"""


DEFENDER_NAME = "Defender"

DEFENDER_CODE = """
def is_ball_in_own_half(ball_position):
    # Considera que la pelota está en campo propio
    # cuando está más cerca del arco propio que del rival.
    return (
        distance(ball_position, own_goal())
        <= distance(ball_position, opponent_goal())
    )


def defensive_position():
    # Define la zona defensiva de referencia del jugador.
    # Se ubica aproximadamente al 25% del recorrido
    # entre el arco propio y el arco rival.
    own = own_goal()
    opponent = opponent_goal()
    _, start_y = starting_position()

    return (
        own[0] + (opponent[0] - own[0]) * 0.25,
        start_y,
    )


def clearance_target():
    # Define una zona segura hacia adelante donde despejar.
    # El defensor no busca un compañero:
    # simplemente aleja la pelota de su propio arco
    # hacia el mediocampo.
    own = own_goal()
    opponent = opponent_goal()

    return (
        own[0] + (opponent[0] - own[0]) * 0.5,
        own[1],
    )


def teammate_near_ball(ball_position, my_ball_distance):
    # Evita que varios compañeros persigan la misma pelota.
    # Cede si otro compañero ya está cerca y mejor posicionado.
    for _, teammate_position in teammates():
        teammate_distance = distance(
            teammate_position,
            ball_position,
        )

        if (
            teammate_distance <= 2.0
            and teammate_distance < my_ball_distance
        ):
            return True

    return False


def move_to(my_position, target):
    target_distance = distance(
        my_position,
        target,
    )

    if target_distance == 0:
        return wait()

    return move(
        direction_to(
            my_position,
            target,
        ),
        speed_for_distance(
            target_distance,
        ),
    )


def play():
    _, my_position = self()
    ball_position, _ = ball()

    # Si la pelota no está en campo propio,
    # vuelve a ocupar su zona defensiva.
    if not is_ball_in_own_half(ball_position):
        return move_to(
            my_position,
            defensive_position(),
        )

    ball_distance = distance(
        my_position,
        ball_position,
    )

    # Si todavía no controla la pelota,
    # decide si debe ir a recuperarla.
    if ball_distance > control_range():

        # Si otro compañero ya está mejor ubicado,
        # mantiene su posición defensiva.
        if teammate_near_ball(
            ball_position,
            ball_distance,
        ):
            return move_to(
                my_position,
                defensive_position(),
            )

        return move_to(
            my_position,
            ball_position,
        )

    # Tiene la pelota bajo control, pero todavía
    # no puede volver a patear.
    if not can_kick():
        return wait()

    # Despeja la pelota hacia el mediocampo
    # en lugar de intentar rematar al arco rival.
    target = clearance_target()

    clear_direction = direction_to(
        ball_position,
        target,
    )

    clear_distance = distance(
        ball_position,
        target,
    )

    return kick(
        clear_direction,
        kick_force_for_distance(
            clear_direction,
            clear_distance,
        ),
    )
"""



MIDFIELDER_NAME = "Midfielder"

MIDFIELDER_CODE = """
def best_teammate_to_pass():
    # Busca al compañero más adelantado,
    # es decir, al que está más cerca del arco rival.
    goal = opponent_goal()

    best_position = None
    best_goal_distance = None

    for _, teammate_position in teammates():
        teammate_goal_distance = distance(
            teammate_position,
            goal,
        )

        if (
            best_goal_distance is None
            or teammate_goal_distance < best_goal_distance
        ):
            best_position = teammate_position
            best_goal_distance = teammate_goal_distance

    return best_position


def teammate_near_ball(ball_position, my_ball_distance):
    # Evita que varios compañeros persigan la misma pelota.
    # Cede si otro compañero ya está cerca y mejor posicionado.
    for _, teammate_position in teammates():
        teammate_distance = distance(
            teammate_position,
            ball_position,
        )

        if (
            teammate_distance <= 2.0
            and teammate_distance < my_ball_distance
        ):
            return True

    return False


def play():
    _, my_position = self()
    ball_position, _ = ball()

    ball_distance = distance(
        my_position,
        ball_position,
    )

    # Si todavía no controla la pelota,
    # decide si debe ir a buscarla.
    if ball_distance > control_range():

        # Si otro compañero ya está disputando la pelota,
        # evita acercarse para reducir choques innecesarios.
        if teammate_near_ball(
            ball_position,
            ball_distance,
        ):
            return wait()

        return move(
            direction_to(
                my_position,
                ball_position,
            ),
            speed_for_distance(
                ball_distance,
            ),
        )

    # Tiene la pelota bajo control, pero todavía
    # no puede volver a patear.
    if not can_kick():
        return wait()

    # El mediocampista no busca rematar al arco.
    # Intenta hacer progresar la jugada pasando la pelota
    # al compañero que está más adelantado.
    teammate_position = best_teammate_to_pass()

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
        0.5,
    )
"""

DEFAULT_BEHAVIORS = (
    {
        "name": ATTACKER_NAME,
        "code": ATTACKER_CODE,
    },
    {
        "name": MIDFIELDER_NAME,
        "code": MIDFIELDER_CODE,
    },
    {
        "name": DEFENDER_NAME,
        "code": DEFENDER_CODE,
    },
)