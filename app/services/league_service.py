from sqlalchemy.orm import Session
from app.core.security import get_password_hash, verify_password
from app.models.league import League, LeagueState, LeaguePrivacy
from app.models.league_participation import LeagueParticipation
from app.models.match_participation import MatchParticipation, MatchRole
from app.models.match import Match, MatchState
from app.models.roster import Roster
from app.models.player_on_roster import PlayerOnRoster
from app.repositories import (
    league_repository,
    league_participation_repository,
    club_repository,
    roster_repository,
    player_repository,
    behavior_repository,
    match_repository,
)

from app.services.fixture_service import generate_fixture

from app.schemas.league import (
    LeagueCreate,
    LeagueJoin,
    FixtureClub,
    FixtureMatchItem,
    StandingRow,
    LeagueDetail,
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


class LeagueForbidden(Exception):
    pass


class InvalidLeagueState(Exception):
    pass


class InsufficientLeagueParticipants(Exception):
    pass


class LeagueNotAvailable(Exception):
    pass


class AlreadyParticipating(Exception):
    pass


class InvalidRoster(Exception):
    pass


class LeagueFull(Exception):
    pass


class InvalidLeaguePassword(Exception):
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
        # get the roster associated with the participation
        roster = participation.roster

        event = build_league_user_event(
            league=league,
            club=club,
            event_type="user_left",
        )

        # felete participation
        league_participation_repository.delete_participation(db=db,participation=participation)
        # felete its associated roster
        roster_repository.delete_roster(db=db,roster=roster)
        # confirm both deletions in the db
        db.commit()
    except Exception:
        db.rollback()
        raise

    try:
        await league_connection_manager.broadcast(
            league_id=league_id,
            state=event,
        )
    finally:
        await league_connection_manager.disconnect_user(
            league_id=league_id,
            user_id=user_id,
        )


async def join_league(
    db: Session,
    league_id: int,
    user_id: int,
    data: LeagueJoin,
) -> tuple[LeagueParticipation, Roster]:
    try:
        club = club_repository.get_by_user_id(
            db=db,
            user_id=user_id,
        )
        league = league_repository.get_by_id(
            db,
            league_id
        )
        if league is None:
            raise LeagueNotFound(
                "League does not exist"
            )
        if league.privacy == LeaguePrivacy.PRIVADA:
            password = data.password
            password_hash = league.password_hash
            if not password:
                raise InvalidLeaguePassword(
                    "This league is private"
                )
            if not verify_password(password, password_hash):
                raise InvalidLeaguePassword(
                    "Incorrect password"
                )
        if league.state != LeagueState.POR_COMENZAR:
            raise LeagueNotAvailable(
                "League is not available"
            )
        existing_participation = (
            league_participation_repository
            .get_participation_by_club_and_league(
                db=db,
                league_id=league_id,
                club_id=club.id,
            )
        )
        if existing_participation is not None:
            raise AlreadyParticipating(
                "Club is already participating in this league"
            )
        participation_count = (
            league_repository.count_participations(
                db=db,
                league_id=league_id
            )
        )
        if participation_count >= league.max_clubs:
            raise LeagueFull(
                "League is full"
            )
        roster = Roster(
            club_id=club.id,
            formation=data.roster.formation,
        )
        roster.players = [
            PlayerOnRoster(
                player_id=player.player_id,
                is_starter=player.is_starter,
                slot=player.slot,
                initial_behavior_id=player.initial_behavior_id,
            )
            for player in data.roster.players
        ]
        try:
            roster.validate_roster()
        except ValueError as error:
            raise InvalidRoster(str(error))
        for p in data.roster.players:
            player = player_repository.get_by_id(
                db,
                p.player_id,
            )
            if player is None:
                raise InvalidRoster(
                    "Player does not exist"
                )
            if player.club_id != club.id:
                raise InvalidRoster(
                    "Player does not belong to user's club"
                )
            if p.initial_behavior_id is not None:
                behavior = behavior_repository.get_by_id(
                    db,
                    p.initial_behavior_id,
                )
                if behavior is None:
                    raise InvalidRoster(
                        "Behavior does not exist"
                    )
                if not behavior.is_default and behavior.club_id != club.id:
                    raise InvalidRoster(
                        "Behavior does not belong to user's club"
                    )
        roster_repository.save(
            db=db,
            roster=roster,
        )
        participation = (
            league_participation_repository.create_participation(
                db=db,
                league_id=league_id,
                club_id=club.id,
                roster_id=roster.id,
            )
        )

        event = build_league_user_event(
            league=league,
            club=club,
            event_type="user_joined",
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    await league_connection_manager.broadcast(
        league_id=league_id,
        state=event,
    )

    return participation, roster


def start_league(
    db: Session,
    league_id: int,
    user_id: int,
    requested_state: LeagueState,
    seed: int | None = None,
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
        
        # draw the fixture and create one match per pair
        participations = league_participation_repository.list_by_league(db, league_id)
        roster_by_club = {p.club_id: p.roster_id for p in participations}
        fixture = generate_fixture(list(roster_by_club), seed) # list(roster_by_club) da las claves del dict, o sea los club_id
        
        # the fixture comes grouped by fecha, match_order keeps that order
        partidos = [partido for fecha in fixture for partido in fecha]
        for order, (local_id, visitante_id) in enumerate(partidos, start=1):
            match = Match(
                id=match_repository.get_next_match_id(db),
                league_id=league_id,
                state=MatchState.POR_COMENZAR,
                match_order=order,
            )
            match.participations = [
                MatchParticipation(
                    club_id=local_id,
                    roster_id=roster_by_club[local_id],
                    role=MatchRole.LOCAL,
                ),
                MatchParticipation(
                    club_id=visitante_id,
                    roster_id=roster_by_club[visitante_id],
                    role=MatchRole.VISITANTE,
                ),
            ]
            db.add(match)

        db.flush()

        
        # persist if no errors
        db.commit()
    except Exception:
        db.rollback()
        raise

# transforms the objects into schemas to send to front
def build_league_state(db: Session, league: League) -> tuple[list[FixtureMatchItem], list[StandingRow]]:
    fixture = []
    for match in league.matches:
        # each match has exactly one local and one visitante
        by_role = {p.role: p for p in match.participations}
        local = by_role[MatchRole.LOCAL]
        visitante = by_role[MatchRole.VISITANTE]
        fixture.append(
            FixtureMatchItem(
                match_id=match.id,
                match_order=match.match_order,
                state=match.state,
                local=FixtureClub(club_id=local.club_id, name=local.club.name),
                visitante=FixtureClub(club_id=visitante.club_id, name=visitante.club.name),
            )
        )

    standings = []
    participations = league_participation_repository.list_by_league(db, league.id)
    for participation in participations:
        standings.append(
            StandingRow(
                club_id=participation.club_id,
                name=participation.club.name,
                points=participation.points,
                matches_played=participation.matches_played,
                matches_won=participation.matches_won,
                matches_drawn=participation.matches_drawn,
                matches_lost=participation.matches_lost,
                goals_for=participation.goals_for,
                goals_against=participation.goals_against,
                goal_difference=participation.goals_for - participation.goals_against,
            )
        )

    return fixture, standings


# league data for the lobby, with fixture and standings once it started
def get_league_detail(db: Session, league_id: int) -> LeagueDetail:
    league = league_repository.get_by_id(
        db=db,
        league_id=league_id,
    )

    if league is None:
        raise LeagueNotFound("League does not exist")

    fixture = None
    standings = None

    # the fixture only exists after the league started
    if league.state == LeagueState.INICIADA:
        fixture, standings = build_league_state(db, league)

    return LeagueDetail(
        league_id=league.id,
        name=league.name,
        state=league.state,
        privacy=league.privacy,
        current_participants=len(league.league_participations),
        capacity=league.max_clubs,
        fixture=fixture,
        standings=standings,
    )
