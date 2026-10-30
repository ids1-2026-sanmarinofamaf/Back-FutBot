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

class BehaviorValidateIn(BaseModel):
    """
    Request payload for validating behavior Python source code.

    Attributes:
        code: Raw Python source code defining the behavior.
    """
    code: str


class BehaviorValidateOut(BaseModel):
    """
    Response payload returned when behavior source code passes validation.

    Attributes:
        valid: Indicates whether the submitted behavior code is valid.
    """
    valid: bool