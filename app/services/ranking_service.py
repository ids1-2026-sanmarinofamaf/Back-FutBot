from sqlalchemy.orm import Session

from app.repositories import ranking_repository
from app.schemas.ranking import RankingItem

def get_global_ranking(db: Session) -> list[RankingItem]:
    rows = ranking_repository.get_global_ranking(db)

    return [
        RankingItem(club_id=row.club_id,club_name=row.club_name,points=row.points)
        for row in rows
    ]