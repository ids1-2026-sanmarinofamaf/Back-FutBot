from enum import Enum
from random import Random

class PenaltySide(Enum):
    LEFT = "LEFT"
    CENTER = "CENTER"
    RIGHT = "RIGHT"


class PenaltyShootout:
    def __init__(
        self,
        club_a_id: int,
        club_b_id: int,
        kickers_a: tuple[int, int, int],
        kickers_b: tuple[int, int, int],
        seed: int,
    ):
        if club_a_id == club_b_id:
            raise ValueError("A club cannot play against itself")

        if (
            len(kickers_a) != 3
            or len(kickers_b) != 3
        ):
            raise ValueError("Each club must have exactly three kickers")

        if (
            len(set(kickers_a)) != 3
            or len(set(kickers_b)) != 3
        ):
            raise ValueError("Kickers must be distinct within each club")

        self.club_a_id = club_a_id
        self.club_b_id = club_b_id
        self.kickers_a = kickers_a
        self.kickers_b = kickers_b
        self.seed = seed

        self.turn: int = 0
        self.score_a: int = 0
        self.score_b: int = 0
        self.winner_club_id: int | None = None
        self._rng = Random(seed)


    def resolve_penalty(
        self,
        kick_side: PenaltySide | None = None,
        save_side: PenaltySide | None = None,
    ) -> dict:
        if self.turn >= 6:
            raise ValueError("Penalty shootout only has 6 rounds")

        for side in (kick_side, save_side):
            if (
                side is not None
                and not isinstance(side, PenaltySide)
            ):
                raise ValueError(
                    "Penalty side must be a PenaltySide or None"
                )

        team = (
            self.club_a_id
            if self.turn % 2 == 0
            else self.club_b_id
        )

        index = self.turn // 2

        kicker = (
            self.kickers_a[index]
            if team == self.club_a_id
            else self.kickers_b[index]
        )

        kick_side = self._resolve_side(kick_side)

        save_side = self._resolve_side(save_side)

        is_goal = kick_side != save_side

        if is_goal:
            if team == self.club_a_id:
                self.score_a += 1

            elif team == self.club_b_id:
                self.score_b += 1

        self.turn += 1

        if self.turn == 6:
            self.winner_club_id = self._resolve_winner()

        return {
            "turn": self.turn,
            "club_id": team,
            "kicker": kicker,
            "kick_side": kick_side.value,
            "save_side": save_side.value,
            "is_goal": is_goal,
            "score_club_a": self.score_a,
            "score_club_b": self.score_b,
        }

    def _resolve_side(
        self,
        side: PenaltySide | None = None,
    ) -> PenaltySide:
        resolve_side = side

        if side is None:
            resolve_side = self._rng.choice(tuple(PenaltySide))

        return resolve_side


    def _resolve_winner(self) -> int:
        winner = (
            self.club_a_id
            if self.score_a > self.score_b
            else self.club_b_id
        )

        if self.score_a == self.score_b:
            winner = self._rng.choice(
                (
                    self.club_a_id,
                    self.club_b_id,
                )
            )

        return winner
