import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.match import Match as PersistedMatch
from app.models.match_participation import MatchParticipation, MatchRole
from app.models.roster import Roster

from app.game.models.match import Match as RuntimeMatch
from app.game.models.ball import Ball
from app.game.constants import FIELD_CENTER, TICS_PER_SECOND

from app.services.match_builder import create_match_participation
from app.services.match_service import (
    load_match_behaviors,
    start_match_task,
)


def load_round_matches(
    db: Session,
    league_id: int,
    round_number: int,
) -> list[PersistedMatch]:
    """
    Load the matches and current rosters for a league round.
    """
    stmt = (
        select(PersistedMatch)
        .where(
            PersistedMatch.league_id == league_id,
            PersistedMatch.round == round_number,
        )
        .options(
            selectinload(PersistedMatch.participations)
            .selectinload(MatchParticipation.roster)
            .selectinload(Roster.players)
        )
        .order_by(PersistedMatch.match_order)
    )

    return list(
        db.scalars(stmt).all()
    )


def build_round_matches(
    db: Session,
    matches: list[PersistedMatch],
    duration_seconds: int,
) -> list[RuntimeMatch]:
    """
    Build runtime matches using the current rosters of a league round.
    """
    runtime_matches = []

    for match in matches:
        participations = {
            participation.role: participation
            for participation in match.participations
        }

        if (
            len(match.participations) != 2
            or set(participations) != {MatchRole.LOCAL, MatchRole.VISITANTE}
        ):
            raise ValueError(
                f"Match {match.id} must have one home and one away club"
            )

        home = participations[MatchRole.LOCAL]
        away = participations[MatchRole.VISITANTE]

        runtime_match = RuntimeMatch(
            match_id=match.id,
            participation_a=create_match_participation(
                db=db,
                roster=home.roster,
                mirror_position=False,
            ),
            participation_b=create_match_participation(
                db=db,
                roster=away.roster,
                mirror_position=True,
            ),
            ball=Ball(
                position=FIELD_CENTER,
                velocity=(0.0, 0.0),
            ),
            duration_ticks=duration_seconds * TICS_PER_SECOND,
        )

        runtime_matches.append(runtime_match)
    
    return runtime_matches


async def run_round_matches(
    db: Session,
    matches: list[RuntimeMatch]
) -> list[RuntimeMatch]:
    """
    Run all matches in a league round concurrently.
    """
    tasks = []

    try:
        for match in matches:
            behaviors = load_match_behaviors(
                db=db,
                match=match,
            )

            task = start_match_task(
                match=match,
                behaviors=behaviors,
            )

            tasks.append(task)

        await asyncio.gather(*tasks)

    except BaseException:
        #Stop all matches if execution or initialization fails
        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )

        raise

    return matches