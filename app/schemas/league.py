from pydantic import BaseModel, Field, model_validator

from app.models.league import LeaguePrivacy


class LeagueCreate(BaseModel):
    """Body de POST /leagues.

    No lleva state (siempre arranca en POR_COMENZAR) ni creator_id (sale del token).
    """
    name: str = Field(min_length=1, max_length=50)
    match_duration: int = Field(gt=0)
    max_clubs: int = Field(ge=3)
    privacy: LeaguePrivacy
    # plain password, it gets hashed in the service
    password: str | None = None

    # private leagues must have a password, public ones must not
    # (an empty string counts as no password, so public leagues may send password: "")
    @model_validator(mode="after")
    def check_privacy_password(self):
        if self.privacy == LeaguePrivacy.PRIVADA and not self.password:
            raise ValueError("Private leagues must have a password")
        if self.privacy == LeaguePrivacy.PUBLICA and self.password:
            raise ValueError("Public leagues cannot have a password")
        return self
