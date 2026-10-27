"""程式進入點。啟動指令：uvicorn app.main:app --reload"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import config, models  # noqa: F401  (import models 才會註冊資料表)
from .migrations import upgrade_database
from .routers import auth, me, pages, vehicles, permits, admin

BASE_DIR = Path(__file__).resolve().parent

upgrade_database()

# 關閉自動產生的 /docs、/openapi.json，減少對外暴露的資訊
app = FastAPI(title="校園車證系統", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
    )
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["Referrer-Policy"] = "no-referrer"
    if not request.url.path.startswith("/static"):
        resp.headers["Cache-Control"] = "no-store"
    if config.COOKIE_SECURE:
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp


# 統一錯誤格式：{"error": 代碼, "message": 說明}；不洩漏堆疊、SQL、使用者輸入的值
@app.exception_handler(StarletteHTTPException)
async def http_error_handler(request: Request, exc: StarletteHTTPException):
    body = exc.detail if isinstance(exc.detail, dict) else {"error": "http_error", "message": str(exc.detail)}
    return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    # FastAPI 預設會把輸入值（包含密碼）原樣回傳，這裡只回傳欄位名稱與原因
    fields = [
        {"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]}
        for e in exc.errors()
    ]
    return JSONResponse(
        {"error": "validation_error", "message": "輸入格式不正確", "fields": fields}, status_code=422
    )


app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(me.router)
app.include_router(vehicles.router)
app.include_router(permits.router)
app.include_router(admin.router)
