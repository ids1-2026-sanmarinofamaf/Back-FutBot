from pydantic import BaseModel


class FriendlyGameLobbyUser(BaseModel):
    user_name: str
    avatar: str
    is_creator: bool 


class FriendlyGameLobbyState(BaseModel):
    friendly_game_id: int
    state: str
    current_users: int
    match_id: int | None
    users: list[FriendlyGameLobbyUser]