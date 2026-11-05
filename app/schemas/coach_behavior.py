from pydantic import BaseModel, ConfigDict, Field


class CoachBehaviorIn(BaseModel):
    name: str = Field(min_length=1)
    code: str = Field(min_length=1)


class CoachBehaviorOut(BaseModel):
    coach_behavior_id: int = Field(validation_alias="id")
    name: str
    code: str
    # allows building it directly from the SQLAlchemy CoachBehavior
    model_config = ConfigDict(from_attributes=True)
