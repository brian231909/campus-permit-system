"""驗證相關 API：註冊、登入、換發 Token、登出。"""
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .. import config
from ..audit import client_ip, write_audit
from ..database import get_db
from ..deps import verify_csrf
from ..models import User, UserSession
from ..schemas import LoginIn, RegisterIn
from ..security import (
    DUMMY_HASH,
    create_access_token,
    encrypt_text,
    hash_password,
    hash_token,
    new_refresh_token,
    utcnow,
    verify_password,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"], dependencies=[Depends(verify_csrf)])

REGISTER_MESSAGE = "註冊申請已送出，請等待管理員啟用帳號。"


def _invalid_credentials() -> HTTPException:
    # 不論是帳號不存在、密碼錯誤、帳號被鎖，都回同一句，避免洩漏帳號是否存在
    return HTTPException(401, detail={"error": "invalid_credentials", "message": "帳號或密碼錯誤"})


def _set_auth_cookies(resp: JSONResponse, access: str, refresh: str) -> None:
    common = dict(httponly=True, secure=config.COOKIE_SECURE, samesite="strict")
    resp.set_cookie(config.ACCESS_COOKIE, access, max_age=config.ACCESS_TOKEN_MINUTES * 60, path="/", **common)
    resp.set_cookie(
        config.REFRESH_COOKIE, refresh, max_age=config.REFRESH_TOKEN_DAYS * 86400,
        path=config.REFRESH_COOKIE_PATH, **common,
    )


def _clear_auth_cookies(resp: JSONResponse) -> None:
    resp.delete_cookie(config.ACCESS_COOKIE, path="/")
    resp.delete_cookie(config.REFRESH_COOKIE, path=config.REFRESH_COOKIE_PATH)


def _unauthorized_response() -> JSONResponse:
    resp = JSONResponse(
        {"error": "unauthorized", "message": "登入已失效，請重新登入"}, status_code=401
    )
    _clear_auth_cookies(resp)
    return resp


def _create_session(db: Session, user: User, request: Request) -> tuple[str, UserSession]:
    """建立新的 session，回傳 (Refresh Token 原值, session)。資料庫只存雜湊。"""
    refresh = new_refresh_token()
    now = utcnow()
    sess = UserSession(
        user_id=user.id,
        token_hash=hash_token(refresh),
        issued_at=now,
        expires_at=now + timedelta(days=config.REFRESH_TOKEN_DAYS),
        ip_address=client_ip(request),
    )
    db.add(sess)
    db.commit()
    return refresh, sess


def _revoke_all_sessions(db: Session, user_id: int, reason: str) -> None:
    db.query(UserSession).filter(
        UserSession.user_id == user_id, UserSession.revoked_at.is_(None)
    ).update({"revoked_at": utcnow(), "revoked_reason": reason})
    db.commit()


# ---------------------------------------------------------------- 註冊
@router.post("/register", status_code=202)
def register(data: RegisterIn, request: Request, db: Session = Depends(get_db)):
    pw_hash = hash_password(data.password)  # 無論帳號是否已存在都先雜湊，回應時間才一致

    existing = (
        db.query(User.id)
        .filter((User.school_id == data.school_id) | (User.email == data.email))
        .first()
    )
    created_user = None
    if existing is None:
        user = User(
            user_type=data.user_type,
            school_id=data.school_id,
            name=data.name,
            email=data.email,
            phone_encrypted=encrypt_text(data.phone) if data.phone else None,
            password_hash=pw_hash,
            role="applicant",       # 一律是申請者；管理員只能由現有管理員指派
            status="pending",       # 等管理員啟用
        )
        db.add(user)
        try:
            db.commit()
            created_user = user
        except IntegrityError:      # 兩個人同時註冊同一個帳號的極端情況
            db.rollback()

    if created_user:
        write_audit(db, request, "register", user_id=created_user.id, target_type="user", target_id=created_user.id)
    else:
        write_audit(db, request, "register_duplicate", result="fail", detail="學號或信箱已存在")

    # 不論成功或重複，回應完全一樣，避免被拿來探測哪些帳號存在
    return {"message": REGISTER_MESSAGE}


# ---------------------------------------------------------------- 登入
@router.post("/login")
def login(data: LoginIn, request: Request, db: Session = Depends(get_db)):
    school_id = data.school_id.strip().upper()
    user = db.query(User).filter(User.school_id == school_id).first()

    # 帳號不存在也驗證一次假雜湊，讓回應時間一致
    password_ok = verify_password(user.password_hash if user else DUMMY_HASH, data.password)
    now = utcnow()

    # 1) 鎖定中：不論密碼對不對都拒絕（也不增加失敗次數）
    if user and user.locked_until and user.locked_until > now:
        write_audit(db, request, "login_blocked", user_id=user.id, result="fail", detail="帳號鎖定中")
        raise _invalid_credentials()

    # 2) 帳號不存在或密碼錯誤
    if user is None or not password_ok:
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= config.MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=config.LOCK_MINUTES)
                user.failed_login_count = 0
                db.commit()
                write_audit(
                    db, request, "account_locked", user_id=user.id, result="fail",
                    detail=f"連續失敗 {config.MAX_FAILED_LOGINS} 次，鎖定 {config.LOCK_MINUTES} 分鐘",
                )
            else:
                db.commit()
        write_audit(
            db, request, "login_failed", user_id=user.id if user else None, result="fail",
            detail=None if user else "unknown_account",  # 不記錄輸入的帳號，避免誤把密碼寫進日誌
        )
        raise _invalid_credentials()

    # 3) 密碼正確，但帳號尚未啟用或已停用（已證明知道密碼，可以告知原因）
    if user.status != "active":
        write_audit(db, request, "login_denied", user_id=user.id, result="fail", detail=f"status={user.status}")
        raise HTTPException(
            403, detail={"error": "account_inactive", "message": "帳號尚未啟用或已停用，請聯絡管理員"}
        )

    # 4) 登入成功
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    refresh, sess = _create_session(db, user, request)  # 內含 commit
    access = create_access_token(user.id, sess.id)
    write_audit(db, request, "login", user_id=user.id, target_type="session", target_id=sess.id)

    resp = JSONResponse({"message": "登入成功", "user": {"name": user.name, "role": user.role}})
    _set_auth_cookies(resp, access, refresh)
    return resp


# ---------------------------------------------------------------- 換發 Token
@router.post("/refresh")
def refresh_token(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(config.REFRESH_COOKIE)
    if not token:
        return _unauthorized_response()

    sess = db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).first()
    now = utcnow()

    if sess is None:
        write_audit(db, request, "refresh_failed", result="fail", detail="unknown_token")
        return _unauthorized_response()

    if sess.revoked_at is not None:
        if sess.revoked_reason == "rotated":
            # 已經換發過的舊 Token 又被拿來用 → 很可能被盜，撤銷該使用者所有登入
            _revoke_all_sessions(db, sess.user_id, "reuse")
            write_audit(
                db, request, "token_reuse_detected", user_id=sess.user_id, result="fail",
                detail="舊 Refresh Token 被重複使用，已撤銷該使用者所有登入",
            )
        else:
            write_audit(db, request, "refresh_failed", user_id=sess.user_id, result="fail", detail="session 已撤銷")
        return _unauthorized_response()

    if sess.expires_at <= now:
        write_audit(db, request, "refresh_failed", user_id=sess.user_id, result="fail", detail="已過期")
        return _unauthorized_response()

    user = db.get(User, sess.user_id)
    if user is None or user.status != "active" or (user.locked_until and user.locked_until > now):
        sess.revoked_at, sess.revoked_reason = now, "user_inactive"
        db.commit()
        write_audit(db, request, "refresh_failed", user_id=sess.user_id, result="fail", detail="帳號非 active 或鎖定中")
        return _unauthorized_response()

    # 輪替：舊的立刻作廢，發新的（兩個動作在同一次 commit，不會只做一半）
    sess.revoked_at, sess.revoked_reason = now, "rotated"
    new_refresh, new_sess = _create_session(db, user, request)
    access = create_access_token(user.id, new_sess.id)
    write_audit(db, request, "token_refresh", user_id=user.id, target_type="session", target_id=new_sess.id)

    resp = JSONResponse({"message": "已更新登入狀態"})
    _set_auth_cookies(resp, access, new_refresh)
    return resp


# ---------------------------------------------------------------- 登出
@router.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get(config.REFRESH_COOKIE)
    if token:
        sess = db.query(UserSession).filter(UserSession.token_hash == hash_token(token)).first()
        if sess and sess.revoked_at is None:
            sess.revoked_at, sess.revoked_reason = utcnow(), "logout"
            db.commit()  # session 被撤銷後，同一個 session 的 Access Token 也立刻失效
            write_audit(db, request, "logout", user_id=sess.user_id, target_type="session", target_id=sess.id)

    resp = JSONResponse({"message": "已登出"})
    _clear_auth_cookies(resp)
    return resp
