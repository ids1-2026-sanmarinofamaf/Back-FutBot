from pydantic import BaseModel, ConfigDict, Field

class BehaviorOut(BaseModel):
    behavior_id: int = Field(validation_alias="id")
    name: str
    code: str
    # allows building it directly from the SQLAlchemy Behavior
    model_config = ConfigDict(from_attributes=True)

class BehaviorCodeOut(BaseModel):
    behavior_id: int = Field(validation_alias="id")
    code: str
    model_config = ConfigDict(from_attributes=True)
