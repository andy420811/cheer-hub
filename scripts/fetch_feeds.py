#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台灣啦啦隊搜尋引擎 — 自動抓取即時新聞(排序+去重+摘要) + YouTube 影片/直播
純 Python 標準庫,無需 pip install。由 GitHub Actions 每小時執行。
輸出: data/feed.json
"""
import json, os, re, sys, html, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "feed.json"
UA = "Mozilla/5.0 (compatible; CheerHubBot/1.1; +https://github.com/andy420811/cheer-hub)"

TEAMS = {
    "rakuten": {"zh": "樂天女孩", "team": "樂天桃猿", "yt": ["RakutenGirls", "RakutenMonkeys"]},
    "fubon":   {"zh": "富邦悍將啦啦隊 Fubon Angels", "team": "富邦悍將", "yt": ["FubonGuardians"]},
    "passion": {"zh": "中信兄弟 Passion Sisters", "team": "中信兄弟", "yt": ["CTBCBrothers"]},
    "uni":     {"zh": "統一獅 Uni-Girls", "team": "統一7-ELEVEn獅", "yt": []},
    "dragon":  {"zh": "味全龍 小龍女 Dragon Beauties", "team": "味全龍", "yt": ["wdragonstv", "wdragons"]},
    "tsg":     {"zh": "台鋼雄鷹啦啦隊 Wing Stars", "team": "台鋼雄鷹", "yt": ["TSGHawks"]},
}
NEWS_ALL_QUERY = "中華職棒 啦啦隊"
NEWS_PER_TEAM = 6
NEWS_ALL = 14
MAX_AGE_DAYS = 7          # 只保留 7 天內的新聞

# ===== IG 動態(透過 Apify Instagram Scraper;需環境變數 APIFY_TOKEN) =====
IG_POSTS = 2              # 每位成員抓幾篇最新貼文
IG_HOURS = {0, 12}        # 只在這些 UTC 整點抓 IG(2 次/天,控制 Apify 免費額度)
IG_ACCOUNTS = [           # 想加人:確認 https://www.instagram.com/<帳號>/ 後照格式加一行
    {"handle": "95_mizuki",     "name": "林襄",   "team": "dragon"},
    {"handle": "le_dahye",      "name": "李多慧", "team": "dragon"},
    {"handle": "wlgus2qh",      "name": "安芝儇", "team": "tsg"},
    {"handle": "muancheoo",     "name": "安琪",   "team": "uni"},
    {"handle": "julieyuan1319", "name": "子筑",   "team": "uni"},
    {"handle": "yt_k14",        "name": "姿琳",   "team": "uni"},
    {"handle": "bacon_she",     "name": "培根",   "team": "uni"},
]
KNOWN_SOURCES = ["ETtoday", "自由時報", "自由", "聯合報", "聯合", "中時", "中國時報", "TVBS",
                 "三立", "東森", "Yahoo", "NOWnews", "運動視界", "麗台", "LINE TODAY",
                 "新頭殼", "壹蘋", "鏡週刊", "鏡報", "民視", "風傳媒", "中央社", "太報", "Nownews"]
YT_VIDEOS = 3

# 重要度:來源權重(可信/大型媒體加分)
SOURCE_WEIGHT = {
    "ETtoday": 3, "自由": 3, "自由時報": 3, "聯合": 3, "中時": 3, "中國時報": 3,
    "TVBS": 2, "三立": 2, "東森": 2, "Yahoo": 2, "NOWnews": 2, "運動視界": 3,
    "麗台運動": 3, "LINE TODAY": 1, "新頭殼": 1, "壹蘋": 2, "鏡週刊": 2, "民視": 2,
}
# 重要度:新聞事件關鍵字加分(轉隊/合約/傷病/冠軍等重大事件)
HOT_WORDS = {
    "轉隊": 5, "加盟": 4, "離隊": 4, "畢業": 3, "退出": 3, "新成員": 3, "新血": 2,
    "隊長": 2, "冠軍": 3, "封王": 3, "受傷": 3, "傷": 1, "合約": 2, "續約": 2,
    "亮相": 2, "首度": 1, "宣布": 2, "回歸": 3, "應援": 1, "寫真": 2, "生日": 1,
    "韓籍": 1, "外援": 2, "人氣": 1, "話題": 1,
}
def http_get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
        return raw.decode("utf-8", "replace"), r.geturl()


def parse_dt(s):
    try:
        d = parsedate_to_datetime(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None


def clean_text(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def detect_source(text):
    for s in KNOWN_SOURCES:
        if s in text:
            return s
    return ""


def score_item(it, now):
    s = 0.0
    dt = it.get("_dt")
    if dt:
        hrs = max(0.0, (now - dt).total_seconds() / 3600)
        s += max(0.0, MAX_AGE_DAYS * 24 - hrs) / 12.0   # 7 天內越新分數越高
    for k, w in SOURCE_WEIGHT.items():
        if k in it.get("source", ""):
            s += w; break
    title = it.get("title", "")
    for k, w in HOT_WORDS.items():
        if k in title:
            s += w
    return s


def norm_title(t):
    return re.sub(r"[\s\W_]+", "", t or "")[:22]


def news_rss(query, limit):
    """Bing News RSS:自帶真實摘要(description)+ 直接連結。"""
    q = urllib.parse.quote(query)
    url = f"https://www.bing.com/news/search?q={q}&format=RSS&setlang=zh-tw&cc=tw"
    out = []
    try:
        xml, _ = http_get(url)
        root = ET.fromstring(xml)
        for item in root.iter("item"):
            title = clean_text(item.findtext("title") or "")
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            summary = clean_text(item.findtext("description") or "")
            if len(summary) > 78:
                summary = summary[:77] + "…"
            source = detect_source(title + " " + summary)
            if title and link:
                out.append({"title": title, "link": link, "source": source, "pub": pub,
                            "summary": summary, "_dt": parse_dt(pub)})
            if len(out) >= limit * 3:
                break
    except Exception as e:
        print(f"  [news] 失敗 {query!r}: {e}", file=sys.stderr)
    return out


def rank_dedupe(items, limit, now):
    seen, uniq = set(), []
    for it in items:
        dt = it.get("_dt")
        if not dt or (now - dt).days > MAX_AGE_DAYS:   # 濾掉 7 天前(或無日期)的舊聞
            continue
        key = norm_title(it["title"])
        if key in seen:
            continue
        seen.add(key)
        it["score"] = round(score_item(it, now), 1)
        uniq.append(it)
    uniq.sort(key=lambda x: x["score"], reverse=True)
    return uniq[:limit]


def finalize(items):
    res = []
    for it in items:
        res.append({"title": it["title"], "link": it["link"], "source": it["source"],
                    "pub": it["pub"], "summary": it.get("summary", ""), "score": it.get("score", 0)})
    return res


def resolve_channel_id(handles):
    for h in handles:
        for url in (f"https://www.youtube.com/@{h}", f"https://www.youtube.com/{h}"):
            try:
                htmltext, _ = http_get(url)
                m = re.search(r'"(?:externalId|channelId)":"(UC[0-9A-Za-z_-]{22})"', htmltext) \
                    or re.search(r'channel/(UC[0-9A-Za-z_-]{22})', htmltext)
                if m:
                    return m.group(1)
            except Exception:
                continue
    return None


def youtube_channel(handles):
    cid = resolve_channel_id(handles)
    if not cid:
        return None
    data = {"channelId": cid,
            "live": f"https://www.youtube.com/embed/live_stream?channel={cid}",
            "channelUrl": f"https://www.youtube.com/channel/{cid}", "videos": []}
    try:
        xml, _ = http_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
        ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        root = ET.fromstring(xml)
        for e in root.findall("a:entry", ns)[:YT_VIDEOS]:
            vid = e.findtext("yt:videoId", default="", namespaces=ns)
            title = clean_text(e.findtext("a:title", default="", namespaces=ns))
            pub = e.findtext("a:published", default="", namespaces=ns) or ""
            if vid:
                data["videos"].append({"id": vid, "title": title, "pub": pub})
    except Exception as e:
        print(f"  [yt] RSS 失敗 {cid}: {e}", file=sys.stderr)
    return data


def instagram_posts(token):
    """透過 Apify 抓 IG_ACCOUNTS 的最新公開貼文;回 {handle小寫: {name,team,handle,posts:[...]}}。"""
    urls = [f"https://www.instagram.com/{a['handle']}/" for a in IG_ACCOUNTS]
    payload = {"directUrls": urls, "resultsType": "posts", "resultsLimit": IG_POSTS, "addParentData": False}
    api = "https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items"
    try:
        req = urllib.request.Request(api, data=json.dumps(payload).encode(),
                                     headers={"Content-Type": "application/json", "User-Agent": UA,
                                              "Authorization": f"Bearer {token}"}, method="POST")
        with urllib.request.urlopen(req, timeout=240) as r:
            items = json.loads(r.read().decode("utf-8", "replace"))
    except Exception as e:
        print(f"  [ig] Apify 失敗: {e}", file=sys.stderr)
        return {}
    meta = {a["handle"].lower(): a for a in IG_ACCOUNTS}
    by = {}
    for it in items if isinstance(items, list) else []:
        u = (it.get("ownerUsername") or "").lower()
        if u not in meta:
            continue
        cap = clean_text(it.get("caption") or "")
        if len(cap) > 95:
            cap = cap[:94] + "…"
        by.setdefault(u, {"name": meta[u]["name"], "team": meta[u]["team"], "handle": meta[u]["handle"], "posts": []})
        by[u]["posts"].append({
            "url": it.get("url") or f"https://www.instagram.com/{meta[u]['handle']}/",
            "img": it.get("displayUrl") or "",
            "caption": cap,
            "time": it.get("timestamp") or "",
            "likes": it.get("likesCount") or 0,
        })
    for u in by:
        by[u]["posts"] = sorted(by[u]["posts"], key=lambda p: p["time"], reverse=True)[:IG_POSTS]
    return by


def build_docs(feed):
    """把 feed 攤平成搜尋索引文件。"""
    docs = []
    for tid, items in feed.get("news", {}).items():
        team = "" if tid == "all" else tid
        for n in items:
            docs.append({"id": "news:" + n["link"], "type": "news", "team": team,
                         "title": n["title"], "text": n.get("summary", ""), "url": n["link"],
                         "time": n.get("pub", ""), "source": n.get("source", "")})
    for tid, y in feed.get("youtube", {}).items():
        for v in y.get("videos", []):
            docs.append({"id": "yt:" + v["id"], "type": "youtube", "team": tid,
                         "title": v["title"], "text": "", "vid": v["id"],
                         "url": "https://www.youtube.com/watch?v=" + v["id"],
                         "time": v.get("pub", ""), "source": "YouTube"})
    for _, acc in feed.get("instagram", {}).items():
        for p in acc.get("posts", []):
            docs.append({"id": "ig:" + p["url"], "type": "ig", "team": acc["team"],
                         "member": acc["name"], "title": acc["name"] + " · IG",
                         "text": p.get("caption", ""), "url": p["url"], "image": p.get("img", ""),
                         "time": p.get("time", ""), "source": "Instagram"})
    return docs


def push_to_index(docs):
    """把文件灌進 Cloudflare Worker 的累積索引(需 CHEER_WORKER_URL + INGEST_KEY)。"""
    url = os.environ.get("CHEER_WORKER_URL", "").strip().rstrip("/")
    key = os.environ.get("INGEST_KEY", "").strip()
    if not url or not key:
        print("索引:未設定 CHEER_WORKER_URL / INGEST_KEY(略過)")
        return
    try:
        req = urllib.request.Request(url + "/ingest", data=json.dumps({"docs": docs}).encode(),
                                     headers={"Content-Type": "application/json", "x-ingest-key": key,
                                              "User-Agent": UA}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as r:
            print("索引:", r.read().decode("utf-8", "replace")[:120])
    except Exception as e:
        print(f"索引 push 失敗: {e}", file=sys.stderr)


def main():
    now = datetime.now(timezone.utc)
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    feed = {"updated": now.isoformat(timespec="seconds"), "news": {}, "youtube": {}, "instagram": {}}

    print("抓取新聞(Bing RSS · 排序+去重+摘要)…")
    feed["news"]["all"] = rank_dedupe(news_rss(NEWS_ALL_QUERY, NEWS_ALL), NEWS_ALL, now)
    for tid, t in TEAMS.items():
        feed["news"][tid] = rank_dedupe(news_rss(f'{t["zh"]} {t["team"]}', NEWS_PER_TEAM), NEWS_PER_TEAM, now)
        print(f"  {tid}: {len(feed['news'][tid])} 則")
    got = sum(1 for it in feed["news"]["all"] if it.get("summary"))
    print(f"  綜合區 {got}/{len(feed['news']['all'])} 則有摘要")

    # 轉成乾淨 JSON(移除內部 _dt)
    for tid in feed["news"]:
        feed["news"][tid] = finalize(feed["news"][tid])

    print("解析 YouTube 頻道…")
    for tid, t in TEAMS.items():
        yt = youtube_channel(t["yt"])
        if yt and yt["videos"]:
            feed["youtube"][tid] = yt
            print(f"  {tid}: {yt['channelId']} · {len(yt['videos'])} 部")
        else:
            print(f"  {tid}: 無頻道影片(新聞仍保留)")

    # IG:只在指定時段抓(省 Apify 額度),其餘時段沿用上次結果
    token = os.environ.get("APIFY_TOKEN", "").strip()
    old_ig = old.get("instagram") or {}
    if token and (now.hour in IG_HOURS or not old_ig):
        print("抓取 IG 動態(Apify)…")
        ig = instagram_posts(token)
        feed["instagram"] = ig if ig else old_ig
        print(f"  取得 {sum(len(v['posts']) for v in feed['instagram'].values())} 篇 IG 貼文")
    else:
        feed["instagram"] = old_ig
        print("IG:本時段沿用上次結果" if token else "IG:未設定 APIFY_TOKEN(略過)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已寫入 {OUT}")

    push_to_index(build_docs(feed))


if __name__ == "__main__":
    main()
