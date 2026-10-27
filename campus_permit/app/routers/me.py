"""個人資料 API（只回傳自己的、且不含雜湊與金鑰）。"""
from fastapi import APIRouter, Depends

from ..deps import AuthContext, get_current_auth

router = APIRouter(prefix="/api/v1", tags=["me"])


@router.get("/me")
def me(ctx: AuthContext = Depends(get_current_auth)):
    u = ctx.user
    return {
        "school_id": u.school_id,
        "name": u.name,
        "email": u.email,
        "user_type": u.user_type,
        "role": u.role,
    }
