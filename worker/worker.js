/**
 * Cloudflare Worker — 啦啦隊搜尋引擎後端代理
 * 讓前端「打關鍵字 → 結果直接顯示在頁面上(不轉跳)」。
 * 提供兩個端點(皆回 JSON、附 CORS):
 *   GET /news?q=關鍵字      → Bing News RSS(標題/連結/摘要/時間/來源)
 *   GET /youtube?q=關鍵字   → YouTube 搜尋結果(videoId/標題)
 *
 * 部署:https://dash.cloudflare.com → Workers & Pages → Create Worker → 貼上本檔 → Deploy
 * 部署後把網址(如 https://xxx.workers.dev)填進 index.html 的 WORKER 常數。
 */
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36";
const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, OPTIONS",
  "Access-Control-Allow-Headers": "*",
};
const json = (obj) => new Response(JSON.stringify(obj), {
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=300", ...CORS },
});
const decodeEnt = (s) => (s || "")
  .replace(/<!\[CDATA\[|\]\]>/g, "")
  .replace(/<[^>]+>/g, " ")
  .replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
  .replace(/&#39;/g, "'").replace(/&amp;/g, "&").replace(/&nbsp;/g, " ")
  .replace(/\s+/g, " ").trim();
const KNOWN = ["ETtoday","自由時報","自由","聯合報","聯合","中時","中國時報","TVBS","三立","東森","Yahoo","NOWnews","運動視界","麗台","LINE TODAY","鏡週刊","鏡報","民視","風傳媒","中央社","太報"];
const src = (t) => { for (const s of KNOWN) if (t.includes(s)) return s; return ""; };

async function fetchText(url) {
  const r = await fetch(url, { headers: { "User-Agent": UA, "Accept-Language": "zh-TW,zh;q=0.9" }, cf: { cacheTtl: 300 } });
  return await r.text();
}

async function news(q) {
  const url = `https://www.bing.com/news/search?q=${encodeURIComponent(q)}&format=RSS&setlang=zh-tw&cc=tw`;
  const xml = await fetchText(url);
  const items = [];
  const blocks = xml.split("<item>").slice(1);
  for (const b of blocks.slice(0, 16)) {
    const pick = (tag) => { const m = b.match(new RegExp(`<${tag}>([\\s\\S]*?)</${tag}>`)); return m ? m[1] : ""; };
    const title = decodeEnt(pick("title"));
    const link = decodeEnt(pick("link"));
    let summary = decodeEnt(pick("description"));
    if (summary.length > 90) summary = summary.slice(0, 89) + "…";
    const pub = decodeEnt(pick("pubDate"));
    if (title && link) items.push({ title, link, summary, pub, source: src(title + " " + summary) });
  }
  return items;
}

async function youtube(q) {
  const url = `https://www.youtube.com/results?search_query=${encodeURIComponent(q)}&hl=zh-TW`;
  const html = await fetchText(url);
  const items = [];
  const seen = new Set();
  const chunks = html.split('"videoRenderer":');
  for (const c of chunks.slice(1)) {
    const idm = c.match(/"videoId":"([\w-]{11})"/);
    const tm = c.match(/"title":\{"runs":\[\{"text":"((?:[^"\\]|\\.)*)"/);
    if (idm && !seen.has(idm[1])) {
      seen.add(idm[1]);
      let title = "";
      try { title = tm ? JSON.parse('"' + tm[1] + '"') : ""; } catch (e) { title = tm ? tm[1] : ""; }
      items.push({ id: idm[1], title });
    }
    if (items.length >= 8) break;
  }
  return items;
}

export default {
  async fetch(request) {
    if (request.method === "OPTIONS") return new Response(null, { headers: CORS });
    const { pathname, searchParams } = new URL(request.url);
    const q = (searchParams.get("q") || "").trim();
    try {
      if (pathname === "/news") return json({ q, items: q ? await news(q) : [] });
      if (pathname === "/youtube") return json({ q, items: q ? await youtube(q) : [] });
      return json({ ok: true, usage: "/news?q=... 或 /youtube?q=..." });
    } catch (e) {
      return json({ error: String(e), items: [] });
    }
  },
};
