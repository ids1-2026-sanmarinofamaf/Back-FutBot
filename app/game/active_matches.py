from app.game.models.match import Match


active_matches: dict[int, Match] = {}

# here only register the match in memory
def register_match(match: Match) -> None:
    match_id = match.match_id

    if match_id <= 0:
        raise ValueError("Invalid match ID")

    if match_id in active_matches:
        raise ValueError(
            f"Match {match_id} is already active"
        )

    active_matches[match_id] = match


def get_match(match_id: int) -> Match | None:
    return active_matches.get(match_id)


def remove_match(match_id: int) -> None:
    active_matches.pop(match_id, None)
