"""Fetch RSS feeds, find a cover image for every article and write news.json.

Runs on GitHub Actions every 15 minutes. The website reads news.json first,
so images show even for feeds (like Google News) that ship no pictures.
"""
import email.utils
import html
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import requests

try:
    from googlenewsdecoder import gnewsdecoder
except Exception:  # pragma: no cover
    gnewsdecoder = None

FEEDS = [
    {"id": "google-news-th", "name": "Google News", "url": ["https://news.google.com/rss?hl=th&gl=TH&ceid=TH:th"], "limit": 25},
    {"id": "thairath", "name": "Thairath", "url": ["https://www.thairath.co.th/rss/news", "https://www.thairath.co.th/rss/news.xml"], "limit": 15},
    {"id": "sanook", "name": "Sanook", "url": ["https://www.sanook.com/news/rss/", "https://www.sanook.com/rss/news.xml", "https://rss.sanook.com/rss.xml"], "limit": 15},
    {"id": "bbc-thai", "name": "BBC Thai", "url": ["https://feeds.bbci.co.uk/thai/rss.xml", "https://www.bbc.com/thai/index.xml"], "limit": 15},
    {"id": "matichon", "name": "มติชน", "url": ["https://www.matichon.co.th/feed"], "limit": 15},
    {"id": "khaosod", "name": "ข่าวสด", "url": ["https://www.khaosod.co.th/feed"], "limit": 15},
    {"id": "bbc-world", "name": "BBC World", "url": ["https://feeds.bbci.co.uk/news/world/rss.xml"], "limit": 10},
]
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
      "Accept-Language": "th-TH,th;q=0.9,en;q=0.8"}
NS = {"media": "http://search.yahoo.com/mrss/", "content": "http://purl.org/rss/1.0/modules/content/"}


def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def img_in_html(s):
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', s or "", re.I)
    return m.group(1) if m else ""


def fix_url(u):
    u = html.unescape((u or "").strip())
    if u.startswith("//"):
        u = "https:" + u
    if u.startswith("http://"):
        u = "https://" + u[7:]
    return u if u.startswith("https://") else ""


def og_image(url):
    try:
        r = requests.get(url, headers=UA, timeout=12)
        page = r.text[:400000]
    except Exception:
        return "", url
    for pat in (r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image',
                r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)',
                r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image'):
        m = re.search(pat, page, re.I)
        if m:
            return fix_url(m.group(1)), r.url
    return "", r.url


def resolve_google(url):
    if gnewsdecoder is None or "news.google.com" not in url:
        return url
    try:
        res = gnewsdecoder(url, interval=1)
        if res.get("status") and res.get("decoded_url"):
            return res["decoded_url"]
        print("  decode failed:", str(res.get("message", res))[:200])
    except Exception as e:
        print("  decode error:", e)
    return url


def parse_feed(feed):
    last = None
    for url in feed["url"]:
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            print(f"  {feed['name']} OK via {url}")
            return parse_root(feed, root)
        except Exception as e:
            print(f"  {feed['name']} {url}: {str(e)[:150]}")
            last = e
    raise last


def parse_root(feed, root):
    out = []
    for it in root.iter("item"):
        title = strip_html(it.findtext("title"))
        if not title:
            continue
        desc = it.findtext("description") or ""
        cont = it.findtext("content:encoded", namespaces=NS) or ""
        img = ""
        for tag in ("media:content", "media:thumbnail"):
            el = it.find(tag, NS)
            if el is not None and el.get("url"):
                img = el.get("url")
                break
        if not img:
            for en in it.findall("enclosure"):
                if (en.get("type") or "image").startswith("image") and en.get("url"):
                    img = en.get("url")
                    break
        img = img or img_in_html(cont) or img_in_html(desc)
        publisher = ""
        if feed["id"] == "google-news-th":
            src = it.find("source")
            publisher = (src.text or "").strip() if src is not None else ""
            m = re.search(r"\s+-\s+([^-]+)$", title)
            if m:
                publisher = publisher or m.group(1).strip()
                title = title[: m.start()]
            summary = f"ที่มา: {publisher}" if publisher else ""
        else:
            summary = strip_html(desc)
        published = ""
        pd = it.findtext("pubDate")
        if pd:
            try:
                published = email.utils.parsedate_to_datetime(pd).astimezone(timezone.utc).isoformat()
            except Exception:
                pass
        out.append({"feedId": feed["id"], "source": feed["name"], "publisher": publisher, "title": title,
                    "link": (it.findtext("link") or "").strip(), "summary": summary[:300],
                    "content": strip_html(cont)[:3000], "imageUrl": fix_url(img), "published": published})
        if len(out) >= feed["limit"]:
            break
    return out


def fill_image(item):
    if item["feedId"] == "google-news-th":
        item["link"] = resolve_google(item["link"])
    if not item["imageUrl"] and item["link"]:
        img, final = og_image(item["link"])
        item["imageUrl"] = img
        if "news.google.com" in item["link"] and "news.google.com" not in final:
            item["link"] = final
    return item


def main():
    items = []
    for feed in FEEDS:
        try:
            got = parse_feed(feed)
            print(f"{feed['name']}: {len(got)} items")
            items += got
        except Exception as e:
            print(f"{feed['name']}: FAILED {str(e)[:150]}")
    google = [i for i in items if i["feedId"] == "google-news-th"]
    others = [i for i in items if i["feedId"] != "google-news-th"]
    for it in google:  # sequential: Google rate-limits the decoder
        fill_image(it)
    with ThreadPoolExecutor(8) as ex:
        others = list(ex.map(fill_image, others))
    items = google + others
    with_img = sum(1 for i in items if i["imageUrl"])
    print(f"total {len(items)} items, {with_img} with images")
    if not items:
        sys.exit("no items fetched; keeping old news.json")
    data = {"updated": datetime.now(timezone.utc).isoformat(), "items": items}
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
