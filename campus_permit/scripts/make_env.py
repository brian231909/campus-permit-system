"""產生 .env（隨機的 JWT 密鑰與資料加密金鑰）。用法：python scripts/make_env.py"""
import os
import secrets
from pathlib import Path

from cryptography.fernet import Fernet

env_path = Path(__file__).resolve().parent.parent / ".env"

if env_path.exists():
    raise SystemExit(".env 已存在，不覆蓋（覆蓋會讓已加密的資料無法解開）。要重來請先自行刪除。")

env_path.write_text(
    f"JWT_SECRET={secrets.token_urlsafe(64)}\n"
    f"DATA_ENCRYPTION_KEY={Fernet.generate_key().decode()}\n"
    "COOKIE_SECURE=false\n"
)
os.chmod(env_path, 0o600)  # 只有自己能讀寫
print(f"已建立 {env_path}")
