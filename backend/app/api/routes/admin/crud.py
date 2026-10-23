"""Generic list/create/update/delete routes for simple admin-managed tables.

No `from __future__ import annotations` here: the route signatures use the
schema classes passed into the factory, which FastAPI must see as real
objects, not strings it would look up in module globals."""
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_admin
from app.core.errors import Conflict, NotFound
from app.db.session import get_db
from app.schemas.common import Page


def crud_router(*, prefix: str, tag: str, model: Any, out: type[BaseModel], create: type[BaseModel],
                update: type[BaseModel], order_by: tuple, filters: dict[str, Any] | None = None,
                delete_hint: str = "") -> APIRouter:
    """filters maps a query-parameter name to the model column it filters."""
    router = APIRouter(prefix=prefix, tags=[tag])
    filters = filters or {}

    @router.get("", response_model=Page[out])
    def list_items(limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0),
                   filter_field: str | None = Query(None, alias="field"), filter_value: str | None = Query(None, alias="value"),
                   _=Depends(get_current_admin), db: Session = Depends(get_db)):
        stmt = select(model)
        if filter_field in filters and filter_value is not None:
            stmt = stmt.where(filters[filter_field] == filter_value)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = db.execute(stmt.order_by(*order_by).limit(limit).offset(offset)).scalars().all()
        return Page(items=items, total=total, limit=limit, offset=offset)

    @router.get("/{item_id}", response_model=out)
    def get_item(item_id: int, _=Depends(get_current_admin), db: Session = Depends(get_db)):
        obj = db.get(model, item_id)
        if obj is None:
            raise NotFound("Not found.")
        return obj

    @router.post("", response_model=out, status_code=201)
    def create_item(data: create, _=Depends(require_admin), db: Session = Depends(get_db)):  # type: ignore[valid-type]
        obj = model(**data.model_dump())
        db.add(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise Conflict("An item with the same unique value (name or slug) already exists.", code="duplicate")
        db.refresh(obj)
        return obj

    @router.patch("/{item_id}", response_model=out)
    def update_item(item_id: int, data: update, _=Depends(require_admin), db: Session = Depends(get_db)):  # type: ignore[valid-type]
        obj = db.get(model, item_id)
        if obj is None:
            raise NotFound("Not found.")
        for k, v in data.model_dump(exclude_unset=True).items():
            setattr(obj, k, v)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise Conflict("Another item already uses that unique value (name or slug).", code="duplicate")
        db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=204)
    def delete_item(item_id: int, _=Depends(require_admin), db: Session = Depends(get_db)):
        obj = db.get(model, item_id)
        if obj is None:
            raise NotFound("Not found.")
        db.delete(obj)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise Conflict(delete_hint or "This item is in use and can't be deleted. Deactivate it instead.",
                           code="in_use")
        return Response(status_code=204)

    return router
