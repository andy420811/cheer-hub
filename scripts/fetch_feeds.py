#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台灣啦啦隊搜尋引擎 — 自動抓取即時新聞 + YouTube 影片/直播
純 Python 標準庫,無需 pip install。由 GitHub Actions 每小時執行。
輸出: data/feed.json
"""
import json, re, sys, urllib.request, urllib.parse, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "feed.json"

UA = "Mozilla/5.0 (compatible; CheerHubBot/1.0; +https://github.com/andy420811/cheer-hub)"

# 六隊：新聞查詢關鍵字 + (可選) YouTube 頻道 handle
TEAMS = {
    "rakuten": {"zh": "樂天女孩", "team": "樂天桃猿", "yt": ["RakutenGirls", "RakutenMonkeys"]},
    "fubon":   {"zh": "富邦悍將啦啦隊 Fubon Angels", "team": "富邦悍將", "yt": ["FubonGuardians"]},
    "passion": {"zh": "中信兄弟 Passion Sisters", "team": "中信兄弟", "yt": ["CTBCBrothers"]},
    "uni":     {"zh": "統一獅 Uni-Girls", "team": "統一7-ELEVEn獅", "yt": []},
    "dragon":  {"zh": "味全龍 小龍女 Dragon Beauties", "team": "味全龍", "yt": ["wdragonstv", "wdragons"]},
    "tsg":     {"zh": "台鋼雄鷹啦啦隊 Wing Stars", "team": "台鋼雄鷹", "yt": ["TSGHawks"]},
}
NEWS_ALL_QUERY = "中華職棒 啦啦隊 OR CPBL 應援團"
NEWS_PER_TEAM = 6
NEWS_ALL = 12
YT_VIDEOS = 3


def http_get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def google_news_rss(query, limit):
    q = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={q}&hl=zh-TW&gl=TW&ceid=TW:zh-Hant"
    out = []
    try:
        xml = http_get(url)
        root = ET.fromstring(xml)
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            src_el = item.find("source")
            source = (src_el.text.strip() if src_el is not None and src_el.text else "")
            # Google News 標題常是 "標題 - 來源"
            if not source and " - " in title:
                source = title.rsplit(" - ", 1)[-1].strip()
            if source and title.endswith(" - " + source):
                title = title[: -(len(source) + 3)].strip()
            if title and link:
                out.append({"title": title, "link": link, "source": source, "pub": pub})
            if len(out) >= limit:
                break
    except Exception as e:
        print(f"  [news] 失敗 {query!r}: {e}", file=sys.stderr)
    return out


def resolve_channel_id(handles):
    """從 handle / 自訂網址解析出 UC... channelId,失敗回 None(該隊就跳過影片)。"""
    for h in handles:
        for url in (f"https://www.youtube.com/@{h}", f"https://www.youtube.com/{h}"):
            try:
                html = http_get(url)
                m = re.search(r'"(?:externalId|channelId)":"(UC[0-9A-Za-z_-]{22})"', html)
                if not m:
                    m = re.search(r'channel/(UC[0-9A-Za-z_-]{22})', html)
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
            "channelUrl": f"https://www.youtube.com/channel/{cid}",
            "videos": []}
    try:
        xml = http_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
        ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
        root = ET.fromstring(xml)
        for entry in root.findall("a:entry", ns)[:YT_VIDEOS]:
            vid = entry.findtext("yt:videoId", default="", namespaces=ns)
            title = (entry.findtext("a:title", default="", namespaces=ns) or "").strip()
            pub = entry.findtext("a:published", default="", namespaces=ns) or ""
            if vid:
                data["videos"].append({"id": vid, "title": title, "pub": pub})
    except Exception as e:
        print(f"  [yt] RSS 失敗 {cid}: {e}", file=sys.stderr)
    return data


def main():
    feed = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "news": {}, "youtube": {}}

    print("抓取新聞…")
    feed["news"]["all"] = google_news_rss(NEWS_ALL_QUERY, NEWS_ALL)
    for tid, t in TEAMS.items():
        feed["news"][tid] = google_news_rss(f'{t["zh"]} {t["team"]}', NEWS_PER_TEAM)
        print(f"  {tid}: {len(feed['news'][tid])} 則")

    print("解析 YouTube 頻道…")
    for tid, t in TEAMS.items():
        yt = youtube_channel(t["yt"])
        if yt:
            feed["youtube"][tid] = yt
            print(f"  {tid}: channel {yt['channelId']} · {len(yt['videos'])} 部影片")
        else:
            print(f"  {tid}: 無頻道(略過影片,新聞仍保留)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"已寫入 {OUT}")


if __name__ == "__main__":
    main()
