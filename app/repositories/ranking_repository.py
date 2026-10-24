from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.club import Club
from app.models.club_statistics import ClubStatistics

# only show the user and his points
def get_global_ranking(db: Session):
    query = (
        select(Club.user_id.label("id_usuario"),ClubStatistics.total_points.label("points"))
        .join(ClubStatistics,Club.id == ClubStatistics.club_id)
        .order_by(ClubStatistics.total_points.desc(), Club.id.asc())
    )

    return db.execute(query).all()