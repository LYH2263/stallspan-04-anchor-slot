from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Vendor
router = APIRouter(prefix="/vendors", tags=["vendors"])

def _serialize(r: Vendor) -> dict:
    return {"id": r.id, "market_day_id": r.market_day_id, "name": r.name,
            "stall_width_m": r.stall_width_m, "priority": r.priority,
            "anchor_m": r.anchor_m, "tolerance_m": r.tolerance_m}

@router.get("")
def list_vendors(db: Session = Depends(get_db)):
    return [_serialize(r)
            for r in db.scalars(select(Vendor).order_by(Vendor.priority, Vendor.id)).all()]

class AnchorUpdate(BaseModel):
    anchor_m: float | None = None
    tolerance_m: float | None = None

@router.patch("/{vendor_id}")
def update_anchor(vendor_id: int, body: AnchorUpdate, db: Session = Depends(get_db)):
    v = db.get(Vendor, vendor_id)
    if not v:
        raise HTTPException(404, "摊主不存在")
    fields = body.model_dump(exclude_unset=True)
    if "anchor_m" in fields:
        if fields["anchor_m"] is None:
            # clearing the anchor clears its tolerance too
            v.anchor_m = None
            v.tolerance_m = None
        else:
            if fields["anchor_m"] < 0:
                raise HTTPException(422, "锚点米标不能为负")
            tol = fields.get("tolerance_m", v.tolerance_m if v.tolerance_m is not None else 0.0)
            if tol is None:
                tol = 0.0
            if tol < 0:
                raise HTTPException(422, "容差不能为负")
            v.anchor_m = fields["anchor_m"]
            v.tolerance_m = tol
    elif "tolerance_m" in fields:
        tol = fields["tolerance_m"]
        if tol is None:
            tol = 0.0
        if tol < 0:
            raise HTTPException(422, "容差不能为负")
        v.tolerance_m = tol
    db.commit()
    db.refresh(v)
    return _serialize(v)
