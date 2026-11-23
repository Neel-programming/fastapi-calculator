"""BREAD routes for calculations. Every route requires a logged-in user."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.calculation_factory import CalculationFactory, build_calculation
from app.database import get_db
from app.models import Calculation, User
from app.schemas import CalculationCreate, CalculationRead

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/calculations",
    tags=["Calculations"],
    responses={401: {"description": "Missing, invalid, or expired token"}},
)

NOT_FOUND = {404: {"description": "Calculation not found"}}
BAD_DATA = {400: {"description": "Invalid a, b, or type"}}


def get_owned_calculation(calc_id: int, user: User, db: Session) -> Calculation:
    """Return the user's calculation, or raise 404 if it is missing or someone else's."""
    calc = db.get(Calculation, calc_id)
    # Another user's calculation gets the same 404, so its existence is not revealed.
    if calc is None or calc.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calculation not found.")
    return calc


@router.get("", response_model=list[CalculationRead])
def browse_calculations(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Browse: list the logged-in user's calculations, oldest first."""
    query = select(Calculation).where(Calculation.user_id == user.id).order_by(Calculation.id)
    return db.scalars(query).all()


@router.get("/{calc_id}", response_model=CalculationRead, responses=NOT_FOUND)
def read_calculation(
    calc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Read: return one of the logged-in user's calculations."""
    return get_owned_calculation(calc_id, user, db)


@router.put("/{calc_id}", response_model=CalculationRead, responses={**NOT_FOUND, **BAD_DATA})
def edit_calculation(
    calc_id: int,
    data: CalculationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Edit: replace a, b, and type, then recompute the result with the factory."""
    calc = get_owned_calculation(calc_id, user, db)
    calc.a = data.a
    calc.b = data.b
    calc.type = data.type.value
    calc.result = CalculationFactory.create(data.type).compute(data.a, data.b)
    db.commit()
    db.refresh(calc)
    logger.info("User %s edited calculation %s", user.id, calc.id)
    return calc


@router.post("", response_model=CalculationRead, status_code=status.HTTP_201_CREATED,
             responses=BAD_DATA)
def add_calculation(
    data: CalculationCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add: compute the result with the factory and save it for the logged-in user."""
    calc = build_calculation(data, user_id=user.id)
    db.add(calc)
    db.commit()
    db.refresh(calc)
    logger.info("User %s added calculation %s", user.id, calc.id)
    return calc


@router.delete("/{calc_id}", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
def delete_calculation(
    calc_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete: remove one of the logged-in user's calculations."""
    calc = get_owned_calculation(calc_id, user, db)
    db.delete(calc)
    db.commit()
    logger.info("User %s deleted calculation %s", user.id, calc_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)