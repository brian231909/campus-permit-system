"""輕量 SQLite 遷移入口。既有資料表保留；新模型由 SQLAlchemy 建立缺少的表。"""
from .database import Base, engine
from . import models  # noqa: F401 - 註冊所有模型

def upgrade_database() -> None:
    # create_all 不會改動既有欄位；本次只新增 vehicles、permit_applications、permit_reviews。
    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "sqlite":
        with engine.begin() as conn:
            conn.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS audit_logs_no_update
                BEFORE UPDATE ON audit_logs BEGIN SELECT RAISE(ABORT, 'audit_logs is append-only'); END;""")
            conn.exec_driver_sql("""CREATE TRIGGER IF NOT EXISTS audit_logs_no_delete
                BEFORE DELETE ON audit_logs BEGIN SELECT RAISE(ABORT, 'audit_logs is append-only'); END;""")
            conn.exec_driver_sql("PRAGMA user_version = 2")
