from pydantic import BaseModel

# for now, it’s like this; perhaps we’ll add more things to the table.
class RankingData(BaseModel):
    points: int

class RankingItem(BaseModel):
    id_usuario: int
    ranking_data: RankingData