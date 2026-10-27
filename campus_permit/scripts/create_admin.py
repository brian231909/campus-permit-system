"""建立第一位管理員。用法（在專案根目錄）：python scripts/create_admin.py"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import ValidationError  # noqa: E402

from app import models  # noqa: E402,F401
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import AuditLog, User  # noqa: E402
from app.schemas import RegisterIn  # noqa: E402
from app.security import hash_password  # noqa: E402

Base.metadata.create_all(bind=engine)

school_id = input("管理員編號（6-12 碼英數字）：").strip()
name = input("姓名：").strip()
email = input("信箱：").strip()
password = getpass.getpass("密碼（至少 12 字元，輸入時不會顯示）：")
if password != getpass.getpass("再輸入一次密碼："):
    raise SystemExit("兩次密碼不一致")

try:
    data = RegisterIn(school_id=school_id, name=name, email=email, user_type="teacher", password=password)
except ValidationError as e:
    for err in e.errors():
        print("輸入有誤：", err["msg"])
    raise SystemExit(1)

with SessionLocal() as db:
    if db.query(User).filter((User.school_id == data.school_id) | (User.email == data.email)).first():
        raise SystemExit("此編號或信箱已存在")
    admin = User(
        user_type="teacher", school_id=data.school_id, name=data.name, email=data.email,
        password_hash=hash_password(data.password), role="admin", status="active",
    )
    db.add(admin)
    db.commit()
    db.add(AuditLog(user_id=admin.id, action="admin_bootstrap", target_type="user", target_id=admin.id,
                    result="success", detail="由命令列建立第一位管理員"))
    db.commit()
    print(f"管理員 {data.school_id} 建立完成")
