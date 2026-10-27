"""申請者車輛管理 API。所有操作均以伺服器端使用者身分限制資料範圍。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from ..audit import write_audit
from ..database import get_db
from ..deps import AuthContext, get_current_auth, verify_csrf
from ..models import PermitApplication, Vehicle
from ..schemas import VehicleIn, VehicleUpdateIn
from ..security import utcnow
router = APIRouter(prefix="/api/v1/vehicles", tags=["vehicles"], dependencies=[Depends(verify_csrf)])

def serialize(v: Vehicle):
    return {"id":v.id,"license_plate":v.license_plate,"vehicle_type":v.vehicle_type,"make_model":v.make_model,"color":v.color,"created_at":v.created_at.isoformat() if v.created_at else None}

@router.get("")
def list_vehicles(ctx: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    q=db.query(Vehicle)
    if ctx.user.role != "admin": q=q.filter(Vehicle.owner_id == ctx.user.id)
    return {"items":[serialize(v) for v in q.order_by(Vehicle.created_at.desc()).all()]}

@router.post("", status_code=201)
def create_vehicle(data: VehicleIn, request: Request, ctx: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    v=Vehicle(owner_id=ctx.user.id, license_plate=data.license_plate, vehicle_type=data.vehicle_type, make_model=data.make_model, color=data.color)
    db.add(v)
    try:
        db.flush()
        write_audit(db, request, "vehicle_create", user_id=ctx.user.id, target_type="vehicle", target_id=v.id, detail=f"license_plate={v.license_plate}")
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, detail={"error":"duplicate_license_plate","message":"此車牌已登錄；每個車牌只能由一個帳號管理，請聯絡管理員處理所有權問題"})
    return serialize(v)

@router.patch("/{vehicle_id}")
def update_vehicle(vehicle_id: int, data: VehicleUpdateIn, request: Request, ctx: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    v=db.get(Vehicle, vehicle_id)
    if not v: raise HTTPException(404, detail={"error":"not_found","message":"找不到車輛"})
    if v.owner_id != ctx.user.id and ctx.user.role != "admin": raise HTTPException(404, detail={"error":"not_found","message":"找不到車輛"})
    if db.query(PermitApplication).filter(PermitApplication.vehicle_id==v.id, PermitApplication.status.in_(["pending","approved"])).first():
        raise HTTPException(409, detail={"error":"vehicle_locked","message":"車輛有待審核或有效車證，不可修改車輛資料；請先處理申請"})
    changes=data.model_dump(exclude_unset=True)
    for k,val in changes.items(): setattr(v,k,val)
    v.updated_at=utcnow()
    write_audit(db, request, "vehicle_update", user_id=ctx.user.id, target_type="vehicle", target_id=v.id, detail="車輛資料已更新")
    return serialize(v)

@router.delete("/{vehicle_id}", status_code=204)
def delete_vehicle(vehicle_id: int, request: Request, ctx: AuthContext = Depends(get_current_auth), db: Session = Depends(get_db)):
    v=db.get(Vehicle, vehicle_id)
    if not v or (v.owner_id != ctx.user.id and ctx.user.role != "admin"):
        raise HTTPException(404, detail={"error":"not_found","message":"找不到車輛"})
    if db.query(PermitApplication).filter(PermitApplication.vehicle_id==v.id).first():
        raise HTTPException(409, detail={"error":"vehicle_has_history","message":"車輛已有申請歷史，為保留稽核紀錄不可刪除"})
    vid=v.id
    db.delete(v)
    db.flush()
    write_audit(db, request, "vehicle_delete", user_id=ctx.user.id, target_type="vehicle", target_id=vid, detail="刪除車輛")
    return None
