from sqlalchemy.orm import Session

from app.models.league import LeagueState

from app.repositories import (
    league_repository,
    league_participation_repository,
    club_repository,
    roster_repository,
)

from app.services.league_websocket_service import (
    league_connection_manager,
    build_league_user_event,
)

# add this classes in order to distinguish the errors
class LeagueNotFound(Exception):
    pass


class LeagueCreatorCannotLeave(Exception):
    pass


class LeagueAlreadyStarted(Exception):
    pass


class LeagueParticipationNotFound(Exception):
    pass


async def leave_league(
    db: Session,
    league_id: int,
    user_id: int,
) -> None:

    try:
        # get the league
        league = league_repository.get_by_id(db=db,league_id=league_id)

        if league is None:
            raise LeagueNotFound("League does not exist")

        # get the user's club
        club = club_repository.get_by_user_id(db=db,user_id=user_id)

        if club is None:
            raise LeagueParticipationNotFound("User is not participating in this league")

        # the creator cannot leave their own league (he only can cancel it)
        if league.creator_id == club.id:
            raise LeagueCreatorCannotLeave("League creator cannot leave the league")

        # the league must not have started
        if league.state != LeagueState.POR_COMENZAR:
            raise LeagueAlreadyStarted("League has already started")

        # check whether the club participates in the league
        participation = (
            league_participation_repository
            .get_participation_by_club_and_league(
                db=db,
                league_id=league_id,
                club_id=club.id,
            )
        )

        if participation is None:
            raise LeagueParticipationNotFound("User is not participating in this league")

        # build the event before 
        event = build_league_user_event(
            league=league,
            club=club,
            event_type="user_left",
        )

        # get the roster associated with the participation
        roster = participation.roster

        # felete participation
        league_participation_repository.delete_participation(db=db,participation=participation)

        # felete its associated roster
        roster_repository.delete_roster(db=db,roster=roster)

        # confirm both deletions in the db
        db.commit()

    except Exception:
        db.rollback()
        raise

    # broadcast the event after a successful commit
    # if we perform the broadcast immediately after the commit, 
    # a websocket error could trigger a rollback, and we don’t want that.
    try:
        await league_connection_manager.broadcast(
            league_id=league_id,
            state=event,
        )
    finally:
        # close all connections belonging to the user
        # who left the league
        await league_connection_manager.disconnect_user(league_id=league_id,user_id=user_id)