from pydantic import BaseModel, ConfigDict, Field

class BehaviorOut(BaseModel):
    behavior_id: int = Field(validation_alias="id")
    name: str
    code: str
    is_default: bool
    # allows building it directly from the SQLAlchemy Behavior
    model_config = ConfigDict(from_attributes=True)

class BehaviorCodeOut(BaseModel):
    behavior_id: int = Field(validation_alias="id")
    code: str
    model_config = ConfigDict(from_attributes=True)

class BehaviorIn(BaseModel):
    """
    Request payload for creating or updating a club behavior.

    Attributes:
        name: Display name of the behavior.
        code: Raw Python source code defining the behavior.
    """
    name: str
    code: str


class BehaviorCreateOut(BaseModel):
    """
    Response payload returned when a new behavior is created.

    Attributes:
        behavior_id: Identifier assigned to the newly created behavior.
    """
    behavior_id: int = Field(validation_alias="id")
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