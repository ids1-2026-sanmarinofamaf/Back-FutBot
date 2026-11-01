from pydantic import BaseModel, Field


class ChangePlayerBehaviorRequest(BaseModel):
    behavior_id: int = Field(gt=0)


class SubstitutionRequest(BaseModel):
    new_player: int
