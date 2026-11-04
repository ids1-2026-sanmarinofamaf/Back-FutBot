

_active_rounds: dict[int, int] = {}


def register_round(
    league_id: int,
    round_number: int,
) -> None:
    if league_id <= 0:
        raise ValueError("Invalid league id")

    if round_number <= 0:
        raise ValueError("Invalid round number")

    if league_id in _active_rounds:
        raise ValueError(f"League {league_id} already has an active round")

    _active_rounds[league_id] = round_number


def get_active_round(league_id: int) -> int | None:
    return _active_rounds.get(league_id)


def remove_round(league_id: int) -> None:
    _active_rounds.pop(league_id, None)
