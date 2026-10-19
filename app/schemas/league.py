from pydantic import BaseModel

from app.models.league import LeagueState


class LeagueUpdate(BaseModel):
    state: LeagueState
