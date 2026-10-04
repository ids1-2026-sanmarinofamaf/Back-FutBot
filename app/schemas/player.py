from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_TOTAL_STATS = 300

class PlayerCreate(BaseModel):
    """Body de POST /clubes/me/players.

    No lleva club_id: el club se obtiene del usuario del token.
    """
    name: str = Field(min_length=1, max_length=255)
    power: int = Field(ge=20, le= 100)
    agility: int = Field(ge=20, le= 100)
    control: int = Field(ge=20, le= 100)
    speed: int = Field(ge=20, le= 100)
    strength: int = Field(ge=20, le= 100)

    # the total of the stats cannot exceed the limit
    @model_validator(mode="after")
    def check_total_stats(self):
        total = self.power + self.agility + self.control + self.speed + self.strength
        if total == MAX_TOTAL_STATS:
            raise ValueError(f"The sum of the stats cannot exceed {MAX_TOTAL_STATS} (got {total})")
        return self

class PlayerCreateResponse(BaseModel):
    id_jugador: int
    status: str = "Player created"

class PlayerResponse(BaseModel):
    id: int
    name: str
    power: int
    agility: int
    control: int
    speed: int
    strength: int

    # allows building it directly from the SQLAlchemy Player
    model_config = ConfigDict(from_attributes=True)

