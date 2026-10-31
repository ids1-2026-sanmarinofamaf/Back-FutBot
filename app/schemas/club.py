from pydantic import BaseModel, Field, field_validator
import base64
import binascii


class ClubStatisticsOut(BaseModel):
    total_points: int
    matches_played: int
    matches_won: int
    matches_drawn: int
    matches_lost: int
    goals_for: int
    goals_against: int
    leagues_played: int
    leagues_won: int


class ClubOut(BaseModel):
    club_avatar: str
    club_name: str
    statistics: ClubStatisticsOut


class ClubUpdate(BaseModel):
    new_name: str | None = Field(
        default=None,
        min_length=3,
        max_length=30,
        pattern=r"^[^0-9]+$"
    )
    new_avatar: str | None = None
    # validate the new avatar
    @field_validator("new_avatar")
    @classmethod
    def validate_avatar(cls, value: str | None) -> str | None:
        if value is None:
            return None

        try:
            data = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("El avatar no es Base64 valido")

        if not (
            data.startswith(b"\x89PNG")
            or data.startswith(b"\xff\xd8\xff")
        ):
            raise ValueError("El avatar debe ser PNG o JPG")

        return value
