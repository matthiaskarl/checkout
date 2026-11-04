"""CRUD endpoints for items."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from checkout.db import SessionDep
from checkout.models import Item
from checkout.schemas import ItemCreate, ItemRead, ItemUpdate

router = APIRouter(prefix="/items", tags=["items"])


def _get_or_404(session: SessionDep, item_id: int) -> Item:
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item not found")
    return item


@router.get("", response_model=list[ItemRead])
def list_items(session: SessionDep, limit: int = 100, offset: int = 0) -> list[Item]:
    stmt = select(Item).order_by(Item.id).limit(limit).offset(offset)
    return list(session.scalars(stmt))


@router.post("", response_model=ItemRead, status_code=status.HTTP_201_CREATED)
def create_item(data: ItemCreate, session: SessionDep) -> Item:
    item = Item(**data.model_dump())
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/{item_id}", response_model=ItemRead)
def get_item(item_id: int, session: SessionDep) -> Item:
    return _get_or_404(session, item_id)


@router.patch("/{item_id}", response_model=ItemRead)
def update_item(item_id: int, data: ItemUpdate, session: SessionDep) -> Item:
    item = _get_or_404(session, item_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    session.commit()
    session.refresh(item)
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, session: SessionDep) -> None:
    session.delete(_get_or_404(session, item_id))
    session.commit()
