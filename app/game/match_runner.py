
from typing import Protocol, Any
import time, asyncio

from app.game.models.match import Match, MatchState, MatchSnapshot
from app.game.models.player_in_match import PlayerInMatch
from app.game.penalties import PenaltyShootout
from app.game.penalty_session import PenaltySession
from app.game.types import CoachCommand, CoachTrigger, Period, Substitution
from app.game.constants import (
    TIC_DURATION,
    MATCH_PERIOD_COUNT,
    HYDRATION_BREAK_DURATION,
    HALFTIME_BREAK_DURATION,
    SUBSTITUTION_EXECUTION_WINDOW,
    PENALTY_INTRO_DURATION,
    PENALTY_RESULT_DURATION,
)
from app.services.match_websocket_service import (
    match_connection_manager,
    build_match_state_message,
    build_coach_changes_message,
    build_coach_substitutions_message,
    build_pause_started_message,
    build_substitution_window_closed_message,
    build_pause_finished_message,
    build_penalty_shootout_started_message,
    build_penalty_turn_started_message,
    build_penalty_result_message,
    build_penalty_shootout_finished_message,
)


class BehaviorCoordinatorProtocol(Protocol):
    def get_actions(self, snapshot: MatchSnapshot) -> Any:
        ...

    def get_coach_assignments(
        self,
        match: Match,
        triggers: list[tuple[int, CoachTrigger]],
    ) -> dict[int, list[CoachCommand]]:
        ...

class GameEngineProtocol(Protocol):
    def step(self, match: Match, snapshot: MatchSnapshot, actions: Any) -> None:
        ...

    def prepare_second_half(self, match: Match) -> None:
        ...

    def reset_positions(self, match: Match) -> None:
        ...

# since not all the classes are implemented yet, we use protocol to simulate them
class MatchRunner:
    def __init__(
        self,
        behavior_coordinator: BehaviorCoordinatorProtocol,
        game_engine: GameEngineProtocol,
        hydration_duration: float = HYDRATION_BREAK_DURATION,
        halftime_duration: float = HALFTIME_BREAK_DURATION,
        execution_window: float = SUBSTITUTION_EXECUTION_WINDOW,
        penalty_intro_duration: float = PENALTY_INTRO_DURATION,
        penalty_result_duration: float = PENALTY_RESULT_DURATION,
    ):
        if (
            execution_window < 0
            or hydration_duration < execution_window
            or halftime_duration < execution_window
        ):
            raise ValueError("Invalid break durations")

        if (
            penalty_intro_duration < 0
            or penalty_result_duration < 0
        ):
            raise ValueError("Invalid penalties duration")

        self.behavior_coordinator = behavior_coordinator
        self.game_engine = game_engine
        self.hydration_duration = hydration_duration
        self.halftime_duration = halftime_duration
        self.execution_window = execution_window
        self.penalty_intro_duration = penalty_intro_duration
        self.penalty_result_duration = penalty_result_duration


    # we implemented the execution of a single tick, and then the cycle of the whole match

    async def execute_tick(self, match: Match) -> None:  # async because we have to wait all the workers
        # apply the behavior changes requested since the last tick (coach and manual)
        applied_assignments = match.apply_pending_behavior_changes()

        # notify the coach changes, only if some coach assignment was applied
        if any(applied_assignments.values()):
            await match_connection_manager.broadcast(
                match.match_id,
                build_coach_changes_message(applied_assignments, match.current_tick),
            )

        snapshot = match.snapshot()     # we make a copy of the match at a specific tick

        actions = await asyncio.to_thread(
            self.behavior_coordinator.get_actions,
            snapshot,
        )

        self.game_engine.step(match,snapshot,actions)   # we update the match state, using the snapshot and actions

        match.current_tick += 1 # update the tick

        # run the coaches triggered during this tick (goals, period start)
        await self._execute_coaches(match)

        # new state after the tick
        new_snapshot = match.snapshot()

        # we format the received state
        message = build_match_state_message(new_snapshot)

        # we sent that new status to everyone connected
        await match_connection_manager.broadcast(match.match_id, message)

    async def _execute_coaches(self, match: Match) -> None:
        # take the triggers and empty the list, so each event runs the coach only once
        triggers = match.pending_coach_triggers
        match.pending_coach_triggers = []

        if not triggers:
            return

        # in a thread, like get_actions, so waiting for the worker does not
        # block the event loop
        commands = await asyncio.to_thread(
            self.behavior_coordinator.get_coach_assignments,
            match,
            triggers,
        )

        for club_id, club_commands in commands.items():
            participation = match.get_participation(club_id)

            for command in club_commands:
                if isinstance(command, Substitution):
                    self._plan_coach_substitution(match, club_id, command)
                else:
                    # keep it for the next tick, where it is validated and applied
                    participation.pending_coach_assignments.append(command)

    @staticmethod
    def _plan_coach_substitution(
        match: Match,
        club_id: int,
        substitution: Substitution,
    ) -> None:
        # an invalid request is discarded without affecting the rest of the list
        try:
            match.plan_substitution(
                club_id=club_id,
                player_out_id=substitution.player_out_id,
                player_in_id=substitution.player_in_id,
                from_coach=True,
            )
        except (ValueError, PermissionError):
            pass

    @staticmethod
    def is_period_end(match: Match) -> bool:
        if (
            match.duration_ticks <= 0
            or match.duration_ticks % MATCH_PERIOD_COUNT != 0
        ):
            return False

        ticks_per_period = match.duration_ticks // MATCH_PERIOD_COUNT

        return (
            0 < match.current_tick < match.duration_ticks
            and match.current_tick % ticks_per_period == 0
        )

    def get_break_config(self, period: Period) -> tuple[str, float]:
        if period == Period.SECOND_QUARTER:
            return "halftime", self.halftime_duration

        if period in (
            Period.FIRST_QUARTER,
            Period.THIRD_QUARTER,
        ):
            return "hydration", self.hydration_duration

        raise ValueError("No break after fourth period")

    async def handle_period_break(self, match: Match) -> None:
        if match.state != MatchState.IN_PROGRESS:
            raise ValueError("Match is not in progress")

        if not self.is_period_end(match):
            raise ValueError("Not at a period boundary")

        finished_period = match.current_period

        pause_type, total_duration = self.get_break_config(finished_period)

        planning_duration = total_duration - self.execution_window

        pause_start = time.monotonic()
        planning_deadline = pause_start + planning_duration
        pause_deadline = pause_start + total_duration

        match.is_paused = True
        match.pause_type = pause_type

        await match_connection_manager.broadcast(
            match.match_id,
            build_pause_started_message(
                pause_type=pause_type,
                duration=total_duration,
                planning_duration=planning_duration,
            ),
        )

        remaining = planning_deadline - time.monotonic()

        if remaining > 0:
            await asyncio.sleep(remaining)

        coach_substitutions = match.close_and_execute_substitutions()

        if coach_substitutions:
            await match_connection_manager.broadcast(
                match.match_id,
                build_coach_substitutions_message(coach_substitutions),
            )

        await match_connection_manager.broadcast(
            match.match_id,
            build_substitution_window_closed_message(
                pause_type=pause_type,
            ),
        )

        remaining = pause_deadline - time.monotonic()

        if remaining > 0:
            await asyncio.sleep(remaining)

        if pause_type == "halftime":
            self.game_engine.prepare_second_half(match)

        self.game_engine.reset_positions(match)

        next_period = Period(finished_period.value + 1)

        match.start_next_period(next_period)

        match.is_paused = False
        match.pause_type = None

        # the coaches run before the first tick of the period, so their
        # assignments apply from that tick (same as the first period)
        await self._execute_coaches(match)

        await match_connection_manager.broadcast(
            match.match_id,
            build_pause_finished_message(
                pause_type=pause_type,
            ),
        )

        new_snapshot = match.snapshot()
        message = build_match_state_message(new_snapshot)

        await match_connection_manager.broadcast(
            match.match_id,
            message,
        )

    async def run_match(self, match: Match) -> Match:
        # first, check that it's a valid match to start
        if match.state != MatchState.NOT_STARTED:
            raise ValueError("Match must be in NOT_STARTED state")

        if match.duration_ticks <= 0:
            raise ValueError("Match duration must be positive")

        if match.duration_ticks % MATCH_PERIOD_COUNT != 0:
            raise ValueError("Match duration must be divisible by 4")

        # change the matchState and execute ticks
        match.state = MatchState.IN_PROGRESS

        # the first period starts with the match, so the coaches run before
        # the first tick and their assignments apply from that tick
        match.register_period_start_triggers()
        await self._execute_coaches(match)

        # send the initial state of the match before executing the first tick
        initial_snapshot = match.snapshot()

        initial_message = build_match_state_message(initial_snapshot)

        await match_connection_manager.broadcast(match.match_id,initial_message)

        next_tick_time = time.monotonic()

        while match.current_tick < match.duration_ticks:
            # execute the tick and all the workers
            await self.execute_tick(match)

            next_tick_time += TIC_DURATION

            remaining_time = next_tick_time - time.monotonic()
            # if the tick ends before TIC_DURATION, we hae to wait the remaining_time
            if remaining_time > 0:
                await asyncio.sleep(remaining_time)

            if self.is_period_end(match):
                await self.handle_period_break(match)
                # eeset the tick clock after a scheduled break
                next_tick_time = time.monotonic()

        winner_id = None

        if (
            match.participation_a.goals
            > match.participation_b.goals
        ):
            winner_id = match.participation_a.club_id

        elif (
            match.participation_a.goals
            < match.participation_b.goals
        ):
            winner_id = match.participation_b.club_id

        match.substitution_requests_open = False

        if (
            winner_id is None
            and match.penalties_enabled
        ):
            await self.run_penalties(
                match=match,
                turn_timeout=5.0,
            )
        else:
            match.winner_club_id = winner_id

        match.state = MatchState.FINISHED

        await match_connection_manager.close_match_connection(match.match_id)

        return match


    async def run_penalties(
        self,
        match: Match,
        turn_timeout: float,
    ) -> None:
        shootout = PenaltyShootout(
            club_a_id=match.participation_a.club_id,
            club_b_id=match.participation_b.club_id,
            kickers_a=_get_penalty_kickers(
                match.participation_a.players,
            ),
            kickers_b=_get_penalty_kickers(
                match.participation_b.players,
            ),
            seed=match.match_id,
        )

        session = PenaltySession(
            shootout=shootout,
            response_timeout=turn_timeout,
        )

        match.penalty_session = session

        try:
            await match_connection_manager.broadcast(
                match.match_id,
                build_penalty_shootout_started_message(
                    self.penalty_intro_duration
                )
            )

            await asyncio.sleep(self.penalty_intro_duration)

            for _ in range(6):
                session.open_turn()

                await match_connection_manager.broadcast(
                    match.match_id,
                    build_penalty_turn_started_message(session),
                )

                result = await session.wait_and_resolve()

                await match_connection_manager.broadcast(
                    match.match_id,
                    build_penalty_result_message(
                        result,
                        self.penalty_result_duration,
                    ),
                )

                await asyncio.sleep(self.penalty_result_duration)

            match.winner_club_id = shootout.winner_club_id

            await match_connection_manager.broadcast(
                match.match_id,
                build_penalty_shootout_finished_message(shootout),
            )

        finally:
            session.accepting_choices = False




def _get_penalty_kickers(
    players: list[PlayerInMatch],
) -> tuple[int, ...]:
    kickers = []

    for player in players:
        if player.is_on_field:
            kickers.append(player.player_id)

    return tuple(kickers)
