from sqlalchemy.orm import Session

from app.models.league import LeagueState

from app.repositories import (
    league_repository,
    league_participation_repository,
    club_repository,
    roster_repository,
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


class LeagueForbidden(Exception):
    pass


class InvalidLeagueState(Exception):
    pass


class InsufficientLeagueParticipants(Exception):
    pass

def leave_league(
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


def start_league(
    db: Session,
    league_id: int,
    user_id: int,
    requested_state: LeagueState,
) -> None:
    try:
        league = league_repository.get_by_id(
            db=db,
            league_id=league_id,
        )

        if league is None:
            raise LeagueNotFound("League does not exist")

        club = club_repository.get_by_user_id(
            db=db,
            user_id=user_id,
        )

        if club is None or league.creator_id != club.id:
            raise LeagueForbidden("Only the league creator can start the league")

        if requested_state != LeagueState.INICIADA:
            raise InvalidLeagueState("Invalid state transition")

        if league.state != LeagueState.POR_COMENZAR:
            raise LeagueAlreadyStarted("League cannot be started")

        # verify that the league has 3 or more participants
        participants_count = (
            league_participation_repository.count_participations(
                db=db,
                league_id=league_id,
            )
        )

        if participants_count < 3:
            raise InsufficientLeagueParticipants("League does not have enough participants")

        # update state
        league_repository.update_state(
            db=db,
            league=league,
            state=LeagueState.INICIADA,
        )

        # persist if no errors
        db.commit()

    except Exception:
        db.rollback()
        raise