# 📣 台灣啦啦隊搜尋引擎 · CPBL Cheer Hub

整合中華職棒六隊啦啦隊的**搜尋引擎入口**:即時新聞、YouTube 直播/影片、IG/Threads/FB 貼文搜尋、應援班表、成員名錄,一站掌握。

🔗 **線上網址**:https://andy420811.github.io/cheer-hub/

## 特色
- 🌗 **日/夜模式**:右上角一鍵切換,記住你的選擇。
- 🔴 **即時新聞**:機器人**每小時**抓 Bing News,**只留 7 天內**、依「時間 × 重要度」排序、**每則附一句摘要**,直接顯示在頁面。
- 📺 **YouTube 影片/直播**:自動嵌入各隊官方頻道最新影片(樂天女孩、富邦、台鋼)。
- 🔎 **頁內即時搜尋(選配)**:部署 Cloudflare Worker 後,新聞/YouTube 搜尋結果**直接顯示在頁面、不轉跳**。
- 📸 **精準社群搜尋**:用 Google `site:` 語法撈某人的 IG / Threads / FB 公開貼文(開新分頁)。
- 🧑‍🤝‍🧑 **成員名錄**:2026 賽季六隊主要成員,點擊直達本人社群。
- 💾 **零維護**:純靜態頁面 + 排程機器人,你的電腦不用開機。

- 📸 **IG 最新貼文牆(選配)**:透過 Apify 每天自動抓人氣成員(林襄、李多慧、安芝儇…)的公開 IG 貼文,圖+caption 直接顯示在頁面。

## (選配)啟用 IG 動態牆 — Apify
1. 到 [apify.com](https://apify.com/) 免費註冊 → **Settings → Integrations** 複製你的 **Personal API token**。
2. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:名稱填 `APIFY_TOKEN`,值貼上 token。
3. **Actions** 分頁手動跑一次「更新即時資料」,IG 牆就會出現。
4. 要加/改成員:編輯 `scripts/fetch_feeds.py` 的 `IG_ACCOUNTS`(先到 `https://www.instagram.com/<帳號>/` 確認帳號正確)。
- 額度:預設 7 位 × 2 篇 × 每天 2 次 ≈ 840 篇/月,在 Apify **免費 2000 篇/月**內。抓太多才會產生費用。
- IG 圖片偶爾會被 CDN 擋(顯示 📸 佔位),點卡片仍可開原文。

## 為什麼「搜尋」無法自動嵌入 IG/FB/Threads 貼文
已實測:Google 與 Bing 的**網頁搜尋都會擋伺服器端抓取**(回 consent/空頁),IG/FB/Threads 也沒有讀「別人貼文」的官方 API,爬蟲違反 ToS 且會壞。新聞能自動抓是因為 Bing News 提供**官方 RSS**;社群平台沒有對應的公開feed。可行的替代:官方 embed 指定貼文、或付費第三方 API。

## (選配)垂直搜尋引擎後端 — Cloudflare Worker + KV
讓搜尋框變成**全文搜尋自建索引**:機器人每次抓的新聞/IG/YouTube 都灌進 KV,累積成可搜尋的資料庫。幾乎全免費(KV 免費額度很大)。

1. **建 Worker**:[dash.cloudflare.com](https://dash.cloudflare.com) → Workers & Pages → **Create → Worker** → 命名(如 `cheer-hub`)→ Deploy → **Edit code** → 貼上 `worker/worker.js` 全部內容 → **Deploy**。
2. **建 KV 並綁定**:左側 **Storage & Databases → KV → Create**(如 `cheer-index`)。回 Worker → **Settings → Bindings → Add → KV namespace**:Variable name 填 **`INDEX`**、選剛建的 namespace → Save。
3. **設密碼**:Worker → **Settings → Variables and Secrets → Add**:名稱 **`INGEST_KEY`**、值自訂一組密碼、選 Encrypt → Save。
4. **複製 Worker 網址**(如 `https://cheer-hub.xxx.workers.dev`)。
5. **讓機器人餵索引**:GitHub repo → Settings → Secrets and variables → Actions,新增兩個 secret:
   - **`CHEER_WORKER_URL`** = 你的 Worker 網址
   - **`INGEST_KEY`** = 跟第 3 步同一組密碼
6. **前端連上**:打開網站 → 頁尾 **⚙️ 設定即時搜尋** → 貼 Worker 網址。
7. 到 **Actions** 手動跑一次;之後每小時累積索引,搜尋框打字按 Enter = 全文搜尋整個索引。

> 只想要「新聞/YouTube 即時搜尋」而不建索引也可以:做完 1、4、6 即可(平台按鈕會走即時 `/news`、`/youtube`)。

## 自動更新是怎麼運作的
`.github/workflows/update.yml` 每小時執行 `scripts/fetch_feeds.py`,抓取新聞與 YouTube RSS,
寫入 `data/feed.json` 並自動 commit。前端 `index.html` 載入時讀取這個 JSON 顯示即時內容。

## 首次部署步驟
1. 把整個資料夾推上 GitHub repo:`andy420811/cheer-hub`(用 `推送更新.bat` 一鍵完成)。
2. 到 repo 的 **Settings → Pages**,Source 選 **Deploy from a branch → main → /(root)**,存檔。
3. 到 **Settings → Actions → General → Workflow permissions**,選 **Read and write permissions**(讓機器人能 commit)。
4. 到 **Actions** 分頁,手動跑一次「更新即時資料」讓新聞立即出現(之後每小時自動)。
5. 打開 https://andy420811.github.io/cheer-hub/ 完成!

## 之後要更新內容
改完檔案後,再次執行 `推送更新.bat` 即可。

## 想加更多隊伍的 YouTube 影片
編輯 `scripts/fetch_feeds.py` 裡 `TEAMS` 的 `yt` 欄位,填入正確的 YouTube 頻道 handle 即可。

## 資料來源
Google News、YouTube、ShowLove 女神百科、cpblgirls 香香百科、CPBL 官方、各隊官網、Yahoo 應援通。
成員頭像為色塊佔位(非真實照片)。名單為 2026 賽季快照,實際異動以各隊官方公告為準。
