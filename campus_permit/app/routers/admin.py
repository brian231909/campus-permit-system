"""管理員專用：申請審核、帳號狀態管理與稽核查詢。"""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from ..audit import write_audit
from ..database import get_db
from ..deps import AuthContext, require_role, verify_csrf
from ..models import AuditLog, PermitApplication, PermitReview, User, Vehicle
from ..schemas import ReviewIn, UserStatusIn
from ..security import utcnow
from .permits import add_one_year, serialize
router=APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(verify_csrf)])

@router.get("/permits")
def admin_list_permits(status:str|None=None, ctx:AuthContext=Depends(require_role("admin")), db:Session=Depends(get_db)):
    allowed={"pending","approved","rejected","cancelled","expired"}
    if status and status not in allowed: raise HTTPException(422,detail={"error":"invalid_status","message":"申請狀態不正確"})
    q=db.query(PermitApplication)
    if status=="expired": q=q.filter(PermitApplication.status=="approved",PermitApplication.valid_until<=utcnow())
    elif status=="approved": q=q.filter(PermitApplication.status=="approved",PermitApplication.valid_until>utcnow())
    elif status: q=q.filter(PermitApplication.status==status)
    items=q.order_by(PermitApplication.submitted_at.asc()).all()
    return {"items":[dict(serialize(p,db),applicant_name=db.get(User,p.applicant_id).name if db.get(User,p.applicant_id) else "") for p in items]}

@router.post("/permits/{permit_id}/review")
def review_permit(permit_id:int,data:ReviewIn,request:Request,ctx:AuthContext=Depends(require_role("admin")),db:Session=Depends(get_db)):
    p=db.query(PermitApplication).filter(PermitApplication.id==permit_id).with_for_update().first()
    if not p: raise HTTPException(404,detail={"error":"not_found","message":"找不到車證申請"})
    if p.status!="pending": raise HTTPException(409,detail={"error":"already_reviewed","message":"此申請已不在待審核狀態"})
    now=utcnow()
    if data.decision=="approved":
        conflict=db.query(PermitApplication).filter(PermitApplication.vehicle_id==p.vehicle_id,PermitApplication.id!=p.id,PermitApplication.status=="approved",PermitApplication.valid_until>now).first()
        if conflict: raise HTTPException(409,detail={"error":"valid_permit_exists","message":"此車輛已有有效車證，不能重複核發"})
        p.status="approved"; p.valid_from=now; p.valid_until=add_one_year(now)
    else:
        p.status="rejected"; p.valid_from=None; p.valid_until=None
    p.reviewed_at=now; p.updated_at=now
    review=PermitReview(application_id=p.id,reviewer_id=ctx.user.id,decision=data.decision,comment=data.comment,created_at=now)
    db.add(review)
    # 業務狀態、審核紀錄及稽核紀錄放在同一個交易中提交。
    db.add(AuditLog(user_id=ctx.user.id,action="permit_review",target_type="permit_application",target_id=p.id,result="success",ip_address=request.client.host if request.client else None,user_agent=(request.headers.get("user-agent") or "")[:200],detail=f"decision={data.decision}; applicant_id={p.applicant_id}"))
    db.commit(); db.refresh(p)
    return {"message":"審核完成","application":serialize(p,db)}

@router.get("/users")
def list_users(ctx:AuthContext=Depends(require_role("admin")),db:Session=Depends(get_db)):
    users=db.query(User).order_by(User.created_at.desc()).all()
    return {"items":[{"id":u.id,"school_id":u.school_id,"name":u.name,"email":u.email,"user_type":u.user_type,"role":u.role,"status":u.status,"created_at":u.created_at.isoformat() if u.created_at else None} for u in users]}

@router.patch("/users/{user_id}/status")
def set_user_status(user_id:int,data:UserStatusIn,request:Request,ctx:AuthContext=Depends(require_role("admin")),db:Session=Depends(get_db)):
    u=db.get(User,user_id)
    if not u: raise HTTPException(404,detail={"error":"not_found","message":"找不到使用者"})
    if u.id==ctx.user.id and data.status!="active": raise HTTPException(409,detail={"error":"self_lockout","message":"不可停用或解除自己的啟用狀態"})
    old=u.status; u.status=data.status
    if data.status!="active":
        from ..models import UserSession
        db.query(UserSession).filter(UserSession.user_id==u.id,UserSession.revoked_at.is_(None)).update({"revoked_at":utcnow(),"revoked_reason":"user_inactive"})
    write_audit(db,request,"user_status_change",user_id=ctx.user.id,target_type="user",target_id=u.id,detail=f"{old}->{data.status}")
    return {"id":u.id,"status":u.status,"message":"帳號狀態已更新"}

@router.get("/audit-logs")
def list_audit_logs(limit:int=100,ctx:AuthContext=Depends(require_role("admin")),db:Session=Depends(get_db)):
    limit=max(1,min(limit,200))
    logs=db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()
    return {"items":[{"id":x.id,"user_id":x.user_id,"action":x.action,"target_type":x.target_type,"target_id":x.target_id,"result":x.result,"detail":x.detail,"created_at":x.created_at.isoformat()} for x in logs]}
