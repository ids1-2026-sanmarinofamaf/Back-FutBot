from sqlalchemy.orm import Session

from app.repositories import ranking_repository
from app.schemas.ranking import RankingItem, RankingData


def get_global_ranking(db: Session) -> list[RankingItem]:
    rows = ranking_repository.get_global_ranking(db)

    return [
        RankingItem(id_usuario=row.id_usuario,ranking_data=RankingData(points=row.points))
        for row in rows
    ]