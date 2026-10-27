"""網頁（Jinja2 模板由後端產生）。"""
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from ..deps import AuthContext, ensure_csrf_cookie, get_optional_auth

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "templates"))


def _render(request: Request, name: str, context: dict | None = None):
    resp = templates.TemplateResponse(request, name, context or {})
    ensure_csrf_cookie(request, resp)
    return resp


@router.get("/")
def index(ctx: AuthContext | None = Depends(get_optional_auth)):
    return RedirectResponse("/dashboard" if ctx else "/login", status_code=303)


@router.get("/login")
def login_page(request: Request, ctx: AuthContext | None = Depends(get_optional_auth)):
    if ctx:
        return RedirectResponse("/dashboard", status_code=303)
    return _render(request, "login.html")


@router.get("/register")
def register_page(request: Request):
    return _render(request, "register.html")


@router.get("/dashboard")
def dashboard(request: Request, ctx: AuthContext | None = Depends(get_optional_auth)):
    if ctx is None:
        return RedirectResponse("/login", status_code=303)
    return _render(request, "dashboard.html", {"user": ctx.user})
