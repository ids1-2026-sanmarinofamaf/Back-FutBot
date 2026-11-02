from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.ranking import RankingItem
from app.services import ranking_service


router = APIRouter(prefix="/ranking",tags=["Ranking"])


@router.get("", response_model=list[RankingItem])
def get_ranking(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    return ranking_service.get_global_ranking(db)