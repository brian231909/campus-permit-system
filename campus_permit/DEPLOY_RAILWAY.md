# Railway 公開部署指南（FastAPI + SQLite）

> 本專案包含登入、車牌及個人資料。請先以測試資料驗證，再決定是否公開給實際使用者。Railway 的公開網址會讓服務可從網際網路連線；請勿在測試前匯入真實敏感資料。

## 1. 上傳到 GitHub

1. 登入 GitHub，建立一個新的 **Private repository**（建議設為私人）。
2. 解壓縮專案，將 `campus_permit` 資料夾中的專案檔案上傳到 repository 根目錄。
3. 確認 `.env`、`*.db`、密碼、金鑰與真實個資沒有被上傳。`.gitignore` 已排除 `.env` 與 `*.db`，仍請在 GitHub 網頁確認。
4. 應上傳 `requirements.txt`、`app/`、`scripts/`、`railway.json` 等程式檔。

## 2. 在 Railway 建立服務

1. 登入 Railway，建立 New Project。
2. 選擇 Deploy from GitHub Repo，連結 GitHub 並選擇此 repository。
3. 等待初次建置；若第一次因缺少必要環境變數而失敗，先完成下一節的 Variables 再重新部署。
4. 在服務的 Settings / Networking（介面名稱可能更新）新增公開網域（Generate Domain）。

## 3. 設定持久化磁碟

SQLite 不能放在暫存檔案系統，否則重新部署或重啟時資料可能遺失。

1. 在 Railway 專案中為此服務新增 Volume。
2. Mount Path 設為 `/data`。
3. 在 Variables 設定 `DATABASE_URL` 為：

   `sqlite:////data/campus_permit.db`

4. 確認 Volume 已掛載在提供給服務的 `/data` 路徑。不要把 `DATABASE_URL` 設成 `sqlite:///./campus_permit.db`。

## 4. 設定機密環境變數

在 Railway 服務的 Variables 中新增：

- `JWT_SECRET`：使用密碼管理器產生至少 32 bytes 隨機值，不能使用範例或公開值。
- `DATA_ENCRYPTION_KEY`：依本專案 `cryptography` 使用方式產生合法 Fernet key；在本機啟用專案環境後執行：

  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

- `COOKIE_SECURE`：設為 `true`。
- `DATABASE_URL`：設為 `sqlite:////data/campus_permit.db`。

金鑰請直接貼到 Railway Variables，不要貼在 GitHub、程式碼、截圖或聊天訊息中。若已有正式資料，變更 `DATA_ENCRYPTION_KEY` 可能使既有加密資料無法解密；請保留原金鑰並先備份。

## 5. 建立第一位管理員

不要在公開註冊功能中開放管理員角色。

部署成功且 Volume 已掛載後，使用 Railway CLI 登入並連結專案／服務，再透過服務的 shell/SSH 功能開啟遠端環境。在遠端專案目錄執行：

`python scripts/create_admin.py`

依提示輸入管理員編號、姓名、信箱與至少 12 字元的密碼。若平台目前方案或介面不提供遠端 shell，請先查閱 Railway CLI/服務 Shell 的最新操作說明，不要改用公開 API 暫時建立管理員，也不要把管理員密碼寫進程式碼。

## 6. 驗證公開網址

1. 開啟 Railway 產生的 `https://...up.railway.app` 網址，確認登入頁可載入。
2. 測試一般使用者註冊與登入、管理員啟用帳號、建立車輛、送出申請及審核。
3. 確認 `COOKIE_SECURE=true` 下 Cookie 可正常使用；如果登入不斷失效，先檢查 HTTPS、Cookie、反向代理及瀏覽器開發者工具，不要為了讓它運作而把正式環境的 Secure Cookie 關掉。
4. 重啟服務後再次確認車輛、帳號與稽核資料仍存在。
5. 確認非管理員無法呼叫管理員 API，且稽核日誌記錄審核行為。

## 7. 備份與限制

- 定期備份 `/data/campus_permit.db`，並在可行時測試還原。
- SQLite 適合小型、單一服務、低至中等寫入量的專題；不適合多個服務實例同時寫同一資料庫。不要水平擴展多個寫入實例共用同一 SQLite 檔案。
- 目前專案仍需補強正式環境的速率限制、MFA、集中式日誌與完整安全測試。公開網址建立後，仍不代表已通過資安認證。
- Railway 的方案、計費及介面可能變更，請在部署前查看官方文件與帳戶目前可用功能。
