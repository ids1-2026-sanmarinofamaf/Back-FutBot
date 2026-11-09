from pydantic import BaseModel, Field

from app.game.penalties import PenaltySide


class ChangePlayerBehaviorRequest(BaseModel):
    behavior_id: int = Field(gt=0)


class SubstitutionRequest(BaseModel):
    new_player: int


class PenaltyChoiceRequest(BaseModel):
    turn: int = Field(gt=0, lt=7)
    side: PenaltySide
