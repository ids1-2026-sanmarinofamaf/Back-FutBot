
from typing import Protocol, Any
import time, asyncio

from app.game.models.match import Match, MatchState, MatchSnapshot
from app.game.models.player_in_match import PlayerInMatch
from app.game.penalties import PenaltyShootout
from app.game.penalty_session import PenaltySession
from app.game.types import Period
from app.game.constants import (
    TIC_DURATION,
    MATCH_PERIOD_COUNT,
    HYDRATION_BREAK_DURATION,
    HALFTIME_BREAK_DURATION,
    SUBSTITUTION_EXECUTION_WINDOW,
)
from app.services.match_websocket_service import (
    match_connection_manager,
    build_match_state_message,
    build_pause_started_message,
    build_substitution_window_closed_message,
    build_pause_finished_message,
    build_penalty_turn_started_message,
    build_penalty_result_message,
    build_penalty_shootout_finished_message,
)


class BehaviorCoordinatorProtocol(Protocol):
    def get_actions(self, snapshot: MatchSnapshot) -> Any:
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
    ):
        if (
            execution_window < 0
            or hydration_duration < execution_window
            or halftime_duration < execution_window
        ):
            raise ValueError("Invalid break durations")

        self.behavior_coordinator = behavior_coordinator
        self.game_engine = game_engine
        self.hydration_duration = hydration_duration
        self.halftime_duration = halftime_duration
        self.execution_window = execution_window

    # we implemented the execution of a single tick, and then the cycle of the whole match

    async def execute_tick(self, match: Match) -> None:  # async because we have to wait all the workers
        snapshot = match.snapshot()     # we make a copy of the match at a specific tick

        actions = await asyncio.to_thread(
            self.behavior_coordinator.get_actions,
            snapshot,
        )

        self.game_engine.step(match,snapshot,actions)   # we update the match state, using the snapshot and actions

        match.current_tick += 1 # update the tick

        # new state after the tick
        new_snapshot = match.snapshot()

        # we format the received state
        message = build_match_state_message(new_snapshot)

        # we sent that new status to everyone connected
        await match_connection_manager.broadcast(match.match_id, message)

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

        match.close_and_execute_substitutions()

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
            for _ in range(6):
                session.open_turn()

                await match_connection_manager.broadcast(
                    match.match_id,
                    build_penalty_turn_started_message(session),
                )

                result = await session.wait_and_resolve()

                await match_connection_manager.broadcast(
                    match.match_id,
                    build_penalty_result_message(result),
                )

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
