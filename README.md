# 📣 台灣啦啦隊搜尋引擎 · CPBL Cheer Hub

整合中華職棒六隊啦啦隊的**搜尋引擎入口**:即時新聞、YouTube 直播/影片、IG/Threads/FB 貼文搜尋、應援班表、成員名錄,一站掌握。

🔗 **線上網址**:https://andy420811.github.io/cheer-hub/

## 特色
- 🔴 **即時新聞**:GitHub Actions 機器人**每小時自動**抓 Google News,顯示六隊最新消息。
- 📺 **YouTube 影片/直播**:自動嵌入各隊官方頻道最新影片(樂天女孩、富邦、台鋼)。
- 🔎 **搜尋引擎**:任何關鍵字一鍵送到 新聞 / IG / Threads / YouTube / X / FB / 百科。
- 📸 **精準社群搜尋**:用 Google `site:` 語法直接撈某人的 IG / Threads / FB 公開貼文。
- 🧑‍🤝‍🧑 **成員名錄**:2026 賽季六隊主要成員,點擊直達本人社群。
- 💾 **零維護**:純靜態頁面 + 排程機器人,你的電腦不用開機。

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
