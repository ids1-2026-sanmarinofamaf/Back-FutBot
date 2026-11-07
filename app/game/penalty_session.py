import asyncio

from time import monotonic

from app.game.penalties import PenaltyShootout, PenaltySide

class PenaltySession:
    def __init__(
        self,
        shootout: PenaltyShootout,
        response_timeout: float,
    ):
        if response_timeout <= 0:
            raise ValueError("Response timeout must be positive")
        
        self.shootout = shootout
        self.response_timeout = response_timeout
        self.choices: dict[int, PenaltySide] = {}
        self.deadline: float | None = None
        self.responses_received = asyncio.Event()
        self.accepting_choices = False


    def open_turn(self) -> None:
        if self.accepting_choices:
            raise ValueError("Penalty session already open")

        if self.shootout.turn >= 6:
            raise ValueError("Penalty session are finished")

        self.choices.clear()
        self.responses_received.clear()

        self.deadline = monotonic() + self.response_timeout

        self.accepting_choices = True


    def submit_choice(
        self,
        club_id: int,
        turn: int,
        side: PenaltySide,
    ) -> None:
        if club_id not in (
            self.shootout.club_a_id,
            self.shootout.club_b_id,
        ):
            raise ValueError(
                "Club is not participating in this shootout"
            )

        if not self.accepting_choices:
            raise ValueError("Penalty turn is closed")

        if turn != self.shootout.turn + 1:
            raise ValueError(
                "Choice does not match the current penalty turn"
            )

        if self.deadline is None:
            raise RuntimeError("Open penalty turn has no deadline")

        if monotonic() >= self.deadline:
            raise ValueError("Penalty turn deadline has passed")

        if not isinstance(side, PenaltySide):
            raise ValueError("Side must be a PenaltySide")

        if club_id in self.choices:
            raise ValueError(
                "Club has already submitted a choice for this turn"
            )

        self.choices[club_id] = side

        if len(self.choices) == 2:
            self.responses_received.set()


    async def wait_and_resolve(self) -> dict:
        if not self.accepting_choices:
            raise ValueError("Penalty turn is closed")

        if self.deadline is None:
            raise RuntimeError("Open penalty turn has no deadline")

        remaining = max(
            0.0,
            self.deadline-monotonic(),
        )

        try:
            if not self.responses_received.is_set():
                await asyncio.wait_for(
                    self.responses_received.wait(),
                    timeout=remaining,
                )

        except TimeoutError:
            # Empty choices resolve later
            pass

        finally:
            self.accepting_choices = False

        if self.shootout.turn % 2 == 0:
            kicking_club_id = self.shootout.club_a_id
            saving_club_id = self.shootout.club_b_id

        else:
            kicking_club_id = self.shootout.club_b_id
            saving_club_id = self.shootout.club_a_id

        return self.shootout.resolve_penalty(
            kick_side=self.choices.get(kicking_club_id),
            save_side=self.choices.get(saving_club_id),
        )
