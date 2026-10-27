"""設定檔：所有機密都從環境變數（.env）讀取，不寫死在程式裡。"""
import os
from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"缺少環境變數 {name}，請先執行：python scripts/make_env.py")
    return value


JWT_SECRET = _require("JWT_SECRET")                    # 簽發 JWT 用的密鑰
DATA_ENCRYPTION_KEY = _require("DATA_ENCRYPTION_KEY")  # 加密電話等個資用的金鑰
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./campus_permit.db")

# 本機用 http 測試時要是 false；正式上線（https）一定要改成 true
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"

ACCESS_TOKEN_MINUTES = 15
REFRESH_TOKEN_DAYS = 7
MAX_FAILED_LOGINS = 5
LOCK_MINUTES = 15

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"  # Refresh Token 只會送到驗證相關 API
