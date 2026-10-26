"""Generic list/create/update/delete routes for simple admin-managed tables.
Every write is permission-checked and written to the audit log (with the
before/after values of changed fields) in the same transaction.

No `from __future__ import annotations` here: the route signatures use the
schema classes passed into the factory, which FastAPI must see as real
objects, not strings it would look up in module globals."""
import enum
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import String, Text, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require
from app.api.tabular import EXPORT_MAX_ROWS, csv_response, like_pattern, ordered, record_export
from app.core.errors import AppError, Conflict, NotFound
from app.core.permissions import Permission
from app.db.session import get_db
from app.models import AdminUser
from app.schemas.common import Page
from app.services import audit


def _plain(v: Any) -> Any:
    return v.value if isinstance(v, enum.Enum) else v


def crud_router(*, prefix: str, tag: str, model: Any, out: type[BaseModel], create: type[BaseModel],
                update: type[BaseModel], order_by: tuple, resource: str, view: Permission, manage: Permission,
                filters: dict[str, Any] | None = None, delete_hint: str = "") -> APIRouter:
    """filters maps a query-parameter name to the model column it filters."""
    router = APIRouter(prefix=prefix, tags=[tag])
    filters = filters or {}
    VIEW, MANAGE, EXPORT = require(view), require(manage), require(Permission.DATA_EXPORT)

    # Data-table support: search the short text columns, sort by any column
    columns = {c.name: c for c in model.__table__.columns}
    searchable = [c for c in model.__table__.columns if isinstance(c.type, String) and not isinstance(c.type, Text)]

    def _query(q: str | None, sort: str | None, order: str, filter_field: str | None, filter_value: str | None):
        stmt = select(model)
        if filter_field in filters and filter_value is not None:
            stmt = stmt.where(filters[filter_field] == filter_value)
        if q and searchable:
            like = like_pattern(q)
            stmt = stmt.where(or_(*[c.like(like) for c in searchable]))
        if sort:
            if sort not in columns:
                raise AppError("Unknown sort column.", code="validation_error", status_code=422,
                               details=[{"field": "sort", "message": "Unknown sort column."}])
            return stmt, ordered(stmt, columns[sort], order, model.id)
        return stmt, stmt.order_by(*order_by)

    def _params(q: str | None = Query(None, max_length=100), sort: str | None = Query(None, max_length=64),
                order: Literal["asc", "desc"] = "asc", filter_field: str | None = Query(None, alias="field"),
                filter_value: str | None = Query(None, alias="value", max_length=100)) -> dict:
        return dict(q=q, sort=sort, order=order, filter_field=filter_field, filter_value=filter_value)

    @router.get("", response_model=Page[out])  # type: ignore[valid-type]
    def list_items(params: dict = Depends(_params), limit: int = Query(100, ge=1, le=200), offset: int = Query(0, ge=0),
                   _: AdminUser = Depends(VIEW), db: Session = Depends(get_db)):
        stmt, sorted_stmt = _query(**params)
        total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = db.execute(sorted_stmt.limit(limit).offset(offset)).scalars().all()
        return Page(items=items, total=total, limit=limit, offset=offset)

    # Before /{item_id}, so "export" is not read as an id
    @router.get("/export", summary="Download as CSV")
    def export_items(request: Request, params: dict = Depends(_params), actor: AdminUser = Depends(EXPORT),
                     db: Session = Depends(get_db)):
        _, sorted_stmt = _query(**params)
        rows = db.execute(sorted_stmt.limit(EXPORT_MAX_ROWS)).scalars().all()
        record_export(request, actor, resource, len(rows), params)
        header = list(out.model_fields)
        return csv_response(prefix.strip("/"), header,
                            ([getattr(out.model_validate(r), h) for h in header] for r in rows))

    @router.get("/{item_id}", response_model=out)
    def get_item(item_id: int, _: AdminUser = Depends(VIEW), db: Session = Depends(get_db)):
        obj = db.get(model, item_id)
        if obj is None:
            raise NotFound("Not found.")
        return obj

    @router.post("", response_model=out, status_code=201)
    def create_item(data: create, request: Request, actor: AdminUser = Depends(MANAGE),  # type: ignore[valid-type]
                    db: Session = Depends(get_db)):
        values = data.model_dump()  # type: ignore[attr-defined]
        obj = model(**values)
        db.add(obj)
        try:
            db.flush()
            audit.record(db, action=f"{resource}.create", actor=actor, resource_type=resource, resource_id=obj.id,
                         details={k: _plain(v) for k, v in values.items()}, request=request)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise Conflict("An item with the same unique value (name or slug) already exists.",
                           code="duplicate") from exc
        db.refresh(obj)
        return obj

    @router.patch("/{item_id}", response_model=out)
    def update_item(item_id: int, data: update, request: Request, actor: AdminUser = Depends(MANAGE),  # type: ignore[valid-type]
                    db: Session = Depends(get_db)):
        obj = db.get(model, item_id)
        if obj is None:
            raise NotFound("Not found.")
        changes = {}
        for k, v in data.model_dump(exclude_unset=True).items():  # type: ignore[attr-defined]
            old = getattr(obj, k)
            if _plain(old) != _plain(v):
                changes[k] = {"from": _plain(old), "to": _plain(v)}
                setattr(obj, k, v)
        try:
            if changes:
                audit.record(db, action=f"{resource}.update", actor=actor, resource_type=resource,
                             resource_id=obj.id, details={"changes": changes}, request=request)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise Conflict("Another item already uses that unique value (name or slug).", code="duplicate") from exc
        db.refresh(obj)
        return obj

    @router.delete("/{item_id}", status_code=204)
    def delete_item(item_id: int, request: Request, actor: AdminUser = Depends(MANAGE),
                    db: Session = Depends(get_db)):
        obj = db.get(model, item_id)
        if obj is None:
            raise NotFound("Not found.")
        snapshot = {c.name: _plain(getattr(obj, c.name)) for c in model.__table__.columns
                    if c.name not in ("created_at", "updated_at")}
        db.delete(obj)
        try:
            db.flush()
            audit.record(db, action=f"{resource}.delete", actor=actor, resource_type=resource, resource_id=item_id,
                         details={"deleted": snapshot}, request=request)
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise Conflict(delete_hint or "This item is in use and can't be deleted. Deactivate it instead.",
                           code="in_use") from exc
        return Response(status_code=204)

    return router
