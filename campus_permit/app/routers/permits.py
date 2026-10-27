"""申請者車證申請與查詢。車證有效期為核准日起一個日曆年。"""
import calendar
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..audit import write_audit
from ..database import get_db
from ..deps import AuthContext, get_current_auth, verify_csrf
from ..models import PermitApplication, PermitReview, Vehicle
from ..schemas import PermitApplyIn
from ..security import utcnow
router=APIRouter(prefix="/api/v1/permits", tags=["permits"], dependencies=[Depends(verify_csrf)])

def add_one_year(dt: datetime) -> datetime:
    year=dt.year+1
    day=min(dt.day, calendar.monthrange(year, dt.month)[1])
    return dt.replace(year=year, day=day)

def current_status(p: PermitApplication, now=None):
    now=now or utcnow()
    if p.status=="approved" and p.valid_until and p.valid_until <= now: return "expired"
    return p.status

def serialize(p: PermitApplication, db: Session):
    v=db.get(Vehicle,p.vehicle_id)
    reviews=db.query(PermitReview).filter(PermitReview.application_id==p.id).order_by(PermitReview.created_at.desc()).all()
    return {"id":p.id,"vehicle_id":p.vehicle_id,"license_plate":v.license_plate if v else None,"vehicle_type":v.vehicle_type if v else None,"purpose":p.purpose,"status":current_status(p),"submitted_at":p.submitted_at.isoformat() if p.submitted_at else None,"reviewed_at":p.reviewed_at.isoformat() if p.reviewed_at else None,"valid_from":p.valid_from.isoformat() if p.valid_from else None,"valid_until":p.valid_until.isoformat() if p.valid_until else None,"reviews":[{"decision":r.decision,"comment":r.comment,"created_at":r.created_at.isoformat()} for r in reviews]}

@router.get("")
def list_permits(ctx: AuthContext=Depends(get_current_auth), db: Session=Depends(get_db)):
    q=db.query(PermitApplication)
    if ctx.user.role != "admin": q=q.filter(PermitApplication.applicant_id==ctx.user.id)
    items=q.order_by(PermitApplication.submitted_at.desc()).all()
    return {"items":[serialize(p,db) for p in items]}

@router.post("",status_code=201)
def apply_permit(data: PermitApplyIn, request: Request, ctx: AuthContext=Depends(get_current_auth), db: Session=Depends(get_db)):
    v=db.get(Vehicle,data.vehicle_id)
    if not v or v.owner_id != ctx.user.id:
        raise HTTPException(404,detail={"error":"vehicle_not_found","message":"找不到你名下的車輛"})
    now=utcnow()
    existing=db.query(PermitApplication).filter(PermitApplication.vehicle_id==v.id, PermitApplication.status=="pending").first()
    if existing: raise HTTPException(409,detail={"error":"pending_application_exists","message":"此車輛已有待審核申請"})
    approved=db.query(PermitApplication).filter(PermitApplication.vehicle_id==v.id, PermitApplication.status=="approved", PermitApplication.valid_until>now).first()
    if approved: raise HTTPException(409,detail={"error":"valid_permit_exists","message":"此車輛目前已有有效車證"})
    p=PermitApplication(applicant_id=ctx.user.id,vehicle_id=v.id,purpose=data.purpose,status="pending",submitted_at=now)
    db.add(p); db.flush()
    write_audit(db,request,"permit_submit",user_id=ctx.user.id,target_type="permit_application",target_id=p.id,detail=f"vehicle_id={v.id}; plate={v.license_plate}")
    return serialize(p,db)

@router.get("/{permit_id}")
def get_permit(permit_id:int, ctx:AuthContext=Depends(get_current_auth), db:Session=Depends(get_db)):
    p=db.get(PermitApplication,permit_id)
    if not p or (p.applicant_id != ctx.user.id and ctx.user.role != "admin"):
        raise HTTPException(404,detail={"error":"not_found","message":"找不到車證申請"})
    return serialize(p,db)

@router.post("/{permit_id}/cancel")
def cancel_permit(permit_id:int, request:Request, ctx:AuthContext=Depends(get_current_auth), db:Session=Depends(get_db)):
    p=db.get(PermitApplication,permit_id)
    if not p or p.applicant_id != ctx.user.id:
        raise HTTPException(404,detail={"error":"not_found","message":"找不到車證申請"})
    if p.status!="pending": raise HTTPException(409,detail={"error":"invalid_state","message":"只有待審核申請可以取消"})
    p.status="cancelled"; p.updated_at=utcnow()
    write_audit(db,request,"permit_cancel",user_id=ctx.user.id,target_type="permit_application",target_id=p.id,detail="申請者取消申請")
    return {"message":"申請已取消","id":p.id,"status":p.status}
