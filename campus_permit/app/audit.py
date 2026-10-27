"""稽核日誌：記錄誰、什麼時候、做了什麼。"""
from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def write_audit(
    db: Session,
    request: Request,
    action: str,
    *,
    user_id: int | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    result: str = "success",
    detail: str | None = None,
) -> None:
    """寫入一筆日誌並 commit。注意：detail 絕對不能放密碼、Token、完整個資。"""
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            result=result,
            ip_address=client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:200],
            detail=detail[:300] if detail else None,
        )
    )
    db.commit()
