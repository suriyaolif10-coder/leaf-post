"""News for หนองบัว INSIDER (nongbua/news.json): Nong Bua Lamphu local news.

Uses the same fetcher as LEAF POST, with Google News searches per district.
Your own stories: GitHub issues titled "[หนองบัว] ...", plus LEAF POST
community stories ("[ชุมชน] ...") that are about Nong Bua Lamphu.
"""
import os
import sys

import requests

sys.path.insert(0, os.path.dirname(__file__))
import fetch_news as fn  # noqa: E402

G = "hl=th&gl=TH&ceid=TH:th"


def search(q, days=7):
    return f"https://news.google.com/rss/search?q={requests.utils.quote(q + f' when:{days}d')}&{G}"


def feed(fid, cat, q, limit=8, days=7):
    return {"id": fid, "name": "Google News", "category": cat, "url": [search(q, days)], "limit": limit}


# order matters: a story found by a district search keeps that district's tab
FEEDS = [
    feed("nb-mueang", "อ.เมือง", '"เมืองหนองบัวลำภู"'),
    feed("nb-naklang", "นากลาง", "นากลาง หนองบัวลำภู"),
    feed("nb-nonsang", "โนนสัง", "โนนสัง หนองบัวลำภู"),
    feed("nb-sribunruang", "ศรีบุญเรือง", "ศรีบุญเรือง"),
    feed("nb-suwannakhuha", "สุวรรณคูหา", "สุวรรณคูหา"),
    feed("nb-nawang", "นาวัง", "นาวัง หนองบัวลำภู"),
    feed("nb-travel", "ท่องเที่ยว", "เที่ยว หนองบัวลำภู", days=30),
    feed("nb-farm", "เกษตร", "เกษตร หนองบัวลำภู", days=14),
    feed("nb-all", "ข่าวหนองบัว", "หนองบัวลำภู", limit=25, days=3),
    feed("nb-isan", "อีสาน", "ข่าวอีสาน", limit=10, days=2),
]

NB_WORDS = ("หนองบัวลำภู", "หนองบัว", "นากลาง", "โนนสัง", "ศรีบุญเรือง", "สุวรรณคูหา", "นาวัง")


def own():
    mine = fn.community_items("[หนองบัว]", "ข่าวชุมชน", "หนองบัว INSIDER")
    shared = [i for i in fn.community_items() if any(w in i["title"] + i.get("content", "") for w in NB_WORDS)]
    seen = {i["uid"] for i in mine}
    return mine + [i for i in shared if i["uid"] not in seen]


if __name__ == "__main__":
    os.makedirs("nongbua", exist_ok=True)
    fn.CACHE.clear()
    fn.main(FEEDS, "nongbua/news.json", own)
