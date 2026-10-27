"""執行資料庫遷移／建立新增資料表。請先備份資料庫。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.migrations import upgrade_database
upgrade_database()
print("資料庫遷移完成（schema version 2）。")
