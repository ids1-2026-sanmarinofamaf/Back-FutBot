from pydantic import BaseModel, Field, model_validator

from app.models.league import LeaguePrivacy

from app.schemas.roster import RosterCreate


class LeagueCreate(BaseModel):
    """Body de POST /leagues.

    No lleva state (siempre arranca en POR_COMENZAR) ni creator_id (sale del token).
    The aliases are the field names of the contract agreed in the SRS.
    """
    name: str = Field(alias="nombre", min_length=1, max_length=50)
    match_duration: int = Field(alias="duracion_partido", gt=0)
    max_clubs: int = Field(alias="max_usuarios", ge=3)
    is_private: bool = Field(alias="es_privada")
    # plain password, it gets hashed in the service
    password: str | None = None
    roster: RosterCreate

    @property
    def privacy(self) -> LeaguePrivacy:
        return LeaguePrivacy.PRIVADA if self.is_private else LeaguePrivacy.PUBLICA

    # private leagues must have a password, public ones must not
    # (an empty string counts as no password, so public leagues may send password: "")
    @model_validator(mode="after")
    def check_privacy_password(self):
        if self.is_private and not self.password:
            raise ValueError("Private leagues must have a password")
        if not self.is_private and self.password:
            raise ValueError("Public leagues cannot have a password")
        return self
