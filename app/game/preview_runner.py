from uuid import UUID

import time, asyncio

from app.game.models.match import (
    Match,
    MatchState,
)

from app.game.behavior_coordinator import BehaviorCoordinator
from app.game.engine import GameEngine
from app.game.constants import TIC_DURATION

from app.services.behavior_preview_websocket_service import preview_connection_manager
from app.services.match_websocket_service import build_match_state_message

from app.schemas.behavior_preview import BehaviorPreviewFinishedMessage


class PreviewRunner:
    def __init__(
        self,
        behavior_coordinator: BehaviorCoordinator,
        game_engine: GameEngine,
    ):
        self.behavior_coordinator = behavior_coordinator
        self.game_engine = game_engine
        self.stop_event = asyncio.Event()


    def stop(self) -> None:
        self.stop_event.set()


    async def execute_tick(
        self,
        preview_id: UUID,
        preview: Match,
    ) -> None:
        snapshot = preview.snapshot()

        actions = self.behavior_coordinator.get_actions(snapshot)

        self.game_engine.step(
            preview,
            snapshot,
            actions
        )

        preview.current_tick += 1

        await preview_connection_manager.broadcast(
            preview_id,
            build_match_state_message(preview.snapshot())
        )


    async def run_preview(
        self,
        preview_id: UUID,
        preview: Match,
    ) -> Match:
        if preview.state != MatchState.NOT_STARTED:
            raise ValueError(
                "Preview must be in NOT_STARTED state"
            )

        if preview.duration_ticks <= 0:
            raise ValueError(
                "Match duration must be positive"
            )

        preview.state = MatchState.IN_PROGRESS

        await preview_connection_manager.broadcast(
            preview_id,
            build_match_state_message(preview.snapshot())
        )

        while (
            preview.current_tick < preview.duration_ticks
            and not self.stop_event.is_set()
        ):
            tick_start = time.monotonic()

            await self.execute_tick(preview_id, preview)

            elapsed = time.monotonic() - tick_start
            remaining_time = TIC_DURATION - elapsed

            if remaining_time > 0:
                try:
                    await asyncio.wait_for(
                        self.stop_event.wait(),
                        timeout=remaining_time,
                    )
                except asyncio.TimeoutError:
                    pass

        preview.state = MatchState.FINISHED

        reason = (
            "stopped"
            if self.stop_event.is_set()
            else "completed"
        )

        await preview_connection_manager.broadcast(
            preview_id,
            BehaviorPreviewFinishedMessage(reason=reason),
        )

        await preview_connection_manager.close_preview_connection(
            preview_id
        )

        return preview