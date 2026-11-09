def resolve_match_winner(
    club_a: tuple[int, int],
    club_b: tuple[int, int],
    winner_club_id: int | None = None,
) -> int | None:
    club_a_id, goals_a = club_a
    club_b_id, goals_b = club_b

    if club_a_id == club_b_id:
        raise ValueError("A club cannot play against itself")

    if goals_a < 0 or goals_b < 0:
        raise ValueError("Goals cannot be negative")

    if (
        winner_club_id is not None
        and winner_club_id not in (club_a_id, club_b_id)
    ):
        raise ValueError("Winner must be a participating club")

    if goals_a == goals_b:
        return winner_club_id

    winner_by_goals = club_a_id if goals_a > goals_b else club_b_id

    if (
        winner_club_id is not None
        and winner_club_id != winner_by_goals
    ):
        raise ValueError("Winner contradicts the regulation score")

    return winner_by_goals
