from itertools import count

from app.game.models.match import Match


active_matches: dict[int, Match] = {}

_match_id_counter = count(1)

# registers a match in memory and assigns it a unique id
# during the lifetime of the backend process.
def register_match(match: Match) -> int:
    match_id = next(_match_id_counter)

    match.match_id = match_id
    active_matches[match_id] = match

    return match_id


def get_match(match_id: int) -> Match | None:
    return active_matches.get(match_id)


def remove_match(match_id: int) -> None:
    active_matches.pop(match_id, None)