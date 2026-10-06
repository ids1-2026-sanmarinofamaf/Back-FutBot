from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.database import get_db
from app.schemas.player import PlayerCreate, PlayerCreateResponse, PlayerResponse
from app.services.player_service import create_player, get_player, list_players


router = APIRouter(
    prefix="/clubes/me/players",
    tags=["Players"]
)


@router.post("",
    response_model=PlayerCreateResponse,
    status_code=status.HTTP_201_CREATED
)

def create(
    data: PlayerCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        player = create_player(
            db=db,
            user_id=current_user.id,
            data=data
        )

        return PlayerCreateResponse(id_jugador=player.id)

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    # persistence failed: the service already did rollback
    except SQLAlchemyError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Player could not be created"
        )
    
@router.get("/{player_id}", response_model=PlayerResponse)
def get_by_id(
    player_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    try:
        return get_player(db=db, user_id=current_user.id, player_id=player_id)

    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

    except LookupError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error))

@router.get("",response_model=list[PlayerResponse])
def get_players(
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        return list_players(db=db, user_id=current_user.id)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))
