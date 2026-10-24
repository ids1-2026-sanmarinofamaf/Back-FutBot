from sqlalchemy.orm import Session

from app.core.security import get_password_hash

from app.schemas.league import LeagueCreate

from app.models.league import League, LeagueState, LeaguePrivacy
from app.models.roster import Roster
from app.models.player_on_roster import PlayerOnRoster

from app.repositories import (
    league_repository,
    league_participation_repository,
    club_repository,
    roster_repository,
    player_repository,
    behavior_repository,
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

class ClubNotFound(Exception):
    pass

def create_league(db: Session, data: LeagueCreate , current_user_id):
    try:
        club = club_repository.get_by_user_id(db, current_user_id)
        if club is None:
            raise ClubNotFound("Club does not exist")

        password_hash = None
        if data.privacy == LeaguePrivacy.PRIVADA:
            password_hash = get_password_hash(data.password)

        # create roster object with the data
        roster = Roster(
            club_id=club.id,
            formation=data.roster.formation
        )

        roster.players = [
                    PlayerOnRoster(
                        player_id=p.player_id,
                        is_starter=p.is_starter,
                        slot=p.slot,
                        initial_behavior_id=p.initial_behavior_id
                    )
                    for p in data.roster.players
        ]
        
        # validate the roster
        roster.validate_roster()

        # playerOnRoster validations
        for p in data.roster.players:
            player = player_repository.get_by_id(db, p.player_id)

            if player is None:
                raise ValueError("Player does not exist")

            if player.club_id != club.id:
                raise ValueError("Player does not belong to user's club")

            if p.initial_behavior_id is not None:
                behavior = behavior_repository.get_by_id(db,p.initial_behavior_id)

                if behavior is None:
                    raise ValueError("Behavior does not exist")

                if not behavior.is_default and behavior.club_id != club.id:
                    raise ValueError("Behavior does not belong to user's club")

    
        # save roster on db
        roster_repository.save(db,roster)

        league = League(
            name = data.name,
            match_duration = data.match_duration,
            max_clubs = data.max_clubs,
            privacy = data.privacy,
            password_hash = password_hash,
            creator_id = club.id
        )
        
        # flush, league.id is assigned here
        league_repository.create(db=db, league=league)

        # the creator joins the league with the roster
        league_participation_repository.create_participation(
            db=db,
            league_id=league.id,
            club_id=club.id,
            roster_id=roster.id,
        )

        # commit league, roster and participation together
        db.commit()
        return league

    except Exception:
        db.rollback()
        raise




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

