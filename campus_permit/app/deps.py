"""共用依賴：登入檢查、角色檢查、CSRF 檢查。每個請求都會經過這裡。"""
import secrets
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from . import config
from .database import get_db
from .models import User, UserSession
from .security import decode_access_token, utcnow


@dataclass
class AuthContext:
    user: User
    session: UserSession


def _auth_from_request(request: Request, db: Session) -> AuthContext | None:
    """依序檢查：Token 有效 → session 沒被撤銷、沒過期 → 帳號狀態是 active。"""
    token = request.cookies.get(config.ACCESS_COOKIE)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload:
        return None
    try:
        uid, sid = int(payload["sub"]), int(payload["sid"])
    except (TypeError, ValueError):
        return None

    sess = db.get(UserSession, sid)
    if sess is None or sess.user_id != uid or sess.revoked_at is not None or sess.expires_at <= utcnow():
        return None
    user = db.get(User, uid)
    if user is None or user.status != "active":
        return None
    return AuthContext(user=user, session=sess)


def get_optional_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext | None:
    return _auth_from_request(request, db)


def get_current_auth(request: Request, db: Session = Depends(get_db)) -> AuthContext:
    ctx = _auth_from_request(request, db)
    if ctx is None:
        raise HTTPException(401, detail={"error": "unauthorized", "message": "請先登入"})
    return ctx


def require_role(*roles: str):
    """預設拒絕：端點必須明確宣告允許的角色。階段 5-3 的管理員 API 會用到。"""

    def checker(ctx: AuthContext = Depends(get_current_auth)) -> AuthContext:
        if ctx.user.role not in roles:
            raise HTTPException(403, detail={"error": "forbidden", "message": "沒有權限"})
        return ctx

    return checker


# ---------- CSRF：Double Submit Cookie ----------
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def verify_csrf(request: Request) -> None:
    """POST/PUT/PATCH/DELETE 必須帶 X-CSRF-Token 標頭，且要和 csrf_token Cookie 相同。"""
    if request.method in SAFE_METHODS:
        return
    cookie = request.cookies.get(config.CSRF_COOKIE)
    header = request.headers.get("x-csrf-token")
    if not cookie or not header or not secrets.compare_digest(cookie, header):
        raise HTTPException(403, detail={"error": "csrf_failed", "message": "CSRF 驗證失敗，請重新整理頁面"})


def ensure_csrf_cookie(request: Request, response: Response) -> None:
    """頁面回應時，若瀏覽器還沒有 CSRF Cookie 就發一個（JS 需要讀取，所以不能是 HttpOnly）。"""
    if not request.cookies.get(config.CSRF_COOKIE):
        response.set_cookie(
            config.CSRF_COOKIE,
            secrets.token_urlsafe(32),
            httponly=False,
            secure=config.COOKIE_SECURE,
            samesite="strict",
            path="/",
        )
