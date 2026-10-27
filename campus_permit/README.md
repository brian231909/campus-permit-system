# 校園車證管理系統（FastAPI + SQLite）

本版本以 `campus_permit_5-1` 為基礎，保留 FastAPI、SQLite、Argon2id、JWT Access Token、Refresh Token 輪替／撤銷、CSRF Double Submit Cookie、手機資料加密及稽核日誌，新增車輛、車證申請、管理員審核、期限管理與帳號管理。

## 業務規則

- 一輛車依車牌管理；車牌正規化為大寫並移除空格，同一車牌只能登錄一次。
- 車輛由建立者管理；申請者只能查看與操作自己名下的車輛及申請。
- 所有車證申請一律進入 `pending`，只能由 `admin` 角色審核。
- 核准時由伺服器設定 `valid_from`，並將 `valid_until` 設為核准日起一個日曆年（閏年日期會安全調整）。使用者不可自行提交核准狀態或期限。
- 同一車輛不能有重複的待審核申請，也不能在仍有有效車證時重複申請／核發。
- 審核結果為 `approved` 或 `rejected`；申請者可在待審核時取消。過期狀態由查詢時計算，管理員可用 `expired` 篩選。
- 有申請歷史的車輛不可刪除，保留關聯與稽核證據。

## 在 Kali Linux / Linux 執行

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip unzip sqlite3
unzip campus_permit_5-1_updated.zip
cd campus_permit
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/make_env.py
python scripts/migrate_db.py
python scripts/create_admin.py
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

瀏覽 `http://127.0.0.1:8000`。管理員建立工具會要求輸入編號、姓名、信箱及至少 12 字元密碼。首次管理員以命令列建立；不要在公開環境使用預設帳號。

## 資料庫遷移

本版 `app/migrations.py` 將 SQLite `PRAGMA user_version` 設為 `2`，並透過 SQLAlchemy `create_all()` 新增不存在的資料表：

- `vehicles`
- `permit_applications`
- `permit_reviews`

既有 `users`、`sessions`、`audit_logs` 不會被刪除或重建；本次沒有要求變更舊欄位。部署前仍請備份 `campus_permit.db`。若未來需要修改既有欄位，應增加正式的逐版遷移腳本，而不是依賴 `create_all()`。遷移後可檢查：

```bash
sqlite3 campus_permit.db 'PRAGMA user_version;'
sqlite3 campus_permit.db '.tables'
sqlite3 campus_permit.db 'PRAGMA foreign_key_check;'
```

若舊資料庫位於其他位置，請先設定 `.env` 的 `DATABASE_URL` 指向原資料庫，再啟動程式。請保留原本 `.env` 的 `JWT_SECRET` 與 `DATA_ENCRYPTION_KEY`，不要重新產生金鑰，否則既有加密電話資料可能無法解密、既有 Token 也會失效。

## API 摘要

### 申請者（登入且帳號 active）

- `GET /api/v1/vehicles`：自己的車輛清單
- `POST /api/v1/vehicles`：新增車輛
- `PATCH /api/v1/vehicles/{vehicle_id}`：修改自己的車輛（有待審核或有效車證時不可修改）
- `DELETE /api/v1/vehicles/{vehicle_id}`：刪除沒有申請歷史的車輛
- `GET /api/v1/permits`、`GET /api/v1/permits/{permit_id}`：查詢自己的申請
- `POST /api/v1/permits`：送出申請
- `POST /api/v1/permits/{permit_id}/cancel`：取消待審核申請

### 管理員

- `GET /api/v1/admin/permits?status=pending`：審核清單，可用 `approved`、`rejected`、`cancelled`、`expired` 篩選
- `POST /api/v1/admin/permits/{permit_id}/review`：核准或駁回
- `GET /api/v1/admin/users`：帳號清單
- `PATCH /api/v1/admin/users/{user_id}/status`：設定 `pending`、`active`、`disabled`
- `GET /api/v1/admin/audit-logs?limit=100`：最近稽核紀錄（上限 200）

所有非安全方法都需同源 CSRF Cookie 與 `X-CSRF-Token` 標頭；網頁已自動處理。API 權限在後端執行，不依賴前端隱藏按鈕。

## 測試流程

1. 建立管理員並登入管理員首頁。
2. 另註冊申請者，管理員於「帳號管理」將其狀態改為啟用。
3. 申請者登入，新增車輛，例如 `ABC-1234`；再用 `abc-1234` 新增應因車牌重複而被拒絕。
4. 申請車證，應顯示「待審核」。申請者不能呼叫管理員審核 API，應回 `403`。
5. 管理員核准後，申請狀態為 `approved`，有效起日是核准時間，截止日為一個日曆年後。
6. 在有效期限內再次申請同車輛，應回 `409`。待審核申請可取消；已核准或已駁回申請不能再取消或重複審核。
7. 申請者不能透過更換 ID 查閱他人的車輛或申請（回 `404`，避免洩漏資源是否存在）。
8. 檢查管理員「稽核日誌」以及資料庫：

```bash
sqlite3 campus_permit.db 'SELECT id, action, result, target_type, target_id, created_at FROM audit_logs ORDER BY id DESC LIMIT 30;'
sqlite3 campus_permit.db 'SELECT id, license_plate, owner_id FROM vehicles;'
sqlite3 campus_permit.db 'SELECT id, vehicle_id, status, valid_from, valid_until FROM permit_applications;'
sqlite3 campus_permit.db 'SELECT application_id, reviewer_id, decision, created_at FROM permit_reviews;'
```

## 自動化測試

完成 `.env` 設定並安裝正式相依套件後，可執行：

```bash
pip install -r requirements-dev.txt
pytest -q tests/
```

目前包含車牌正規化、核准日起一個日曆年（含閏年）及有效期限判斷的單元測試。整合流程亦應依上方手動測試清單驗證登入、越權、申請、審核、重複車牌及有效期限。

## 重要安全說明

- SQLite 觸發器只阻止一般 SQL `UPDATE`／`DELETE` 修改稽核表，不代表能抵抗具有資料庫檔案權限的攻擊者；正式部署需限制檔案權限、備份並考慮外部集中式日誌。
- 本版尚未內建 Rate Limiting、TOTP MFA、電子郵件驗證、資料庫加密及正式反向代理設定。正式上線必須使用 HTTPS、將 `COOKIE_SECURE=true`、保護 `.env`、設定備份與監控，並完成安全測試。
- 車牌唯一性採全系統唯一。如果校方政策允許車牌移轉，應由管理員建立經稽核的車輛所有權轉移流程，不要直接修改資料庫。
- 管理員可檢視所有車輛與申請；只有管理員可審核。前端 UI 不是安全邊界，後端路由才是權限判定來源。
