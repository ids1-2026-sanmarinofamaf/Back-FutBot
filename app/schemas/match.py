from pydantic import BaseModel


class SubstitutionRequest(BaseModel):
    new_player: int