from pydantic import BaseModel

# for now, it’s like this; perhaps we’ll add more things to the table.
class RankingItem(BaseModel):
    club_id: int
    club_name: str
    points: int