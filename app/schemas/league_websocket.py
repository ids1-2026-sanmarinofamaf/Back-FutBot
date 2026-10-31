from typing import Literal
from pydantic import BaseModel

# the info of the user
class LeagueLobbyUser(BaseModel):
    club_id: int
    user_name: str
    avatar: str
    is_creator: bool

# the info that will be sended to the user when he join a new league
class LeagueLobbyState(BaseModel):
    type: Literal["lobby_state"] = "lobby_state"
    league_id: int
    state: str
    current_users: int
    users: list[LeagueLobbyUser]


class LeagueUserEvent(BaseModel):
    type: Literal["user_joined", "user_left"]
    league_id: int
    user: LeagueLobbyUser
