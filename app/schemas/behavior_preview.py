from uuid import UUID

from pydantic import BaseModel, Field


class BehaviorPreviewCreate(BaseModel):
    code: str = Field(min_length=1)
    behavior_teammate_1: int = Field(gt=0)
    behavior_teammate_2: int = Field(gt=0)


class BehaviorPreviewCreateResponse(BaseModel):
    preview_id: UUID