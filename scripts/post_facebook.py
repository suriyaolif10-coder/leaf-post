"""Post news to the Facebook Page.

- Your own community stories: posted as soon as their page is live.
- General headlines: one post every FB_POST_EVERY_MIN minutes (default 120),
  skipped at night (01:00-06:00 Bangkok time).
Already-posted stories are remembered in posted.json so nothing is posted twice.

Needs two repository secrets: FB_PAGE_ID and FB_PAGE_TOKEN.
"""
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import requests

from build_pages import page_url

GRAPH = "https://graph.facebook.com"
BKK = timezone(timedelta(hours=7))
STATE_FILE = "posted.json"
MAX_OWN_PER_RUN = 3


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            s = json.load(f)
    except Exception:
        s = {}
    s.setdefault("posted", [])
    s.setdefault("last_general", "")
    return s


def save_state(s):
    s["posted"] = s["posted"][-1500:]
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(s, f, ensure_ascii=False, indent=1)


def tag(text):
    return "#" + re.sub(r"[\s.,:;!?/\\()\[\]{}'\"#@&+*%-]+", "", text or "")


def post(page_id, token, message, link):
    r = requests.post(f"{GRAPH}/{page_id}/feed", timeout=30,
                      data={"message": message, "link": link, "access_token": token})
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.ok and data.get("id"):
        print("  posted:", data["id"])
        return True
    err = data.get("error", {})
    print(f"  FAILED ({r.status_code}): {err.get('message', r.text[:200])}")
    if err.get("code") in (190, 200, 10):  # bad/expired token or missing permission
        print("  -> token problem: create a new Page token and update FB_PAGE_TOKEN")
        sys.exit(0)
    return False


def page_is_live(url, wait=240):
    """GitHub Pages needs a minute or two to publish a new page."""
    end = time.time() + wait
    while True:
        try:
            if requests.get(url, timeout=15, headers={"Cache-Control": "no-cache"}).status_code == 200:
                return True
        except Exception:
            pass
        if time.time() > end:
            return False
        time.sleep(15)


def main():
    page_id, token = os.environ.get("FB_PAGE_ID", "").strip(), os.environ.get("FB_PAGE_TOKEN", "").strip()
    if not page_id or not token:
        print("Facebook not set up yet (add FB_PAGE_ID and FB_PAGE_TOKEN secrets) - skipping")
        return
    with open("news.json", encoding="utf-8") as f:
        items = json.load(f).get("items", [])
    state = load_state()
    done = set(state["posted"])
    first_run = not state["posted"] and not state["last_general"]

    # 1) your own community stories
    own = [i for i in items if i.get("own") and i.get("uid") and i["uid"] not in done]
    own.sort(key=lambda i: i.get("published", ""))
    for it in own[:MAX_OWN_PER_RUN]:
        url = page_url(it["uid"])
        if not page_is_live(url):
            print("  page not live yet, will post next run:", url)
            continue
        summary = (it.get("content") or it.get("summary") or "").strip()
        if len(summary) > 400:
            summary = summary[:400].rstrip() + "…"
        msg = f"📢 {it['title']}\n\n{summary}\n\n{tag('ลีฟโพสต์')} {tag('ข่าวชุมชน')}"
        if it.get("place"):
            msg += " " + tag(it["place"].split()[0])
        print("own:", it["title"][:60])
        if post(page_id, token, msg, url):
            state["posted"].append(it["uid"])

    # 2) one general headline every N minutes, not at night
    every = int(os.environ.get("FB_POST_EVERY_MIN", "120"))
    now = datetime.now(BKK)
    last = datetime.fromisoformat(state["last_general"]) if state["last_general"] else None
    if 1 <= now.hour < 6:
        print("night time - no general post")
    elif last and now - last < timedelta(minutes=every):
        print(f"general: next post after {(last + timedelta(minutes=every)).strftime('%H:%M')}")
    else:
        pool = [i for i in items if not i.get("own") and i.get("imageUrl") and i.get("link", "").startswith("http")
                and "news.google.com" not in i["link"] and i["link"] not in done]
        pool.sort(key=lambda i: i.get("published", ""), reverse=True)
        pool = pool[:15]
        if pool:
            it = random.choice(pool)
            who = it.get("publisher") or it.get("source") or ""
            msg = f"{it['title']}\n\nที่มา: {who}\n\n{tag('ลีฟโพสต์')} {tag(it.get('category', 'ข่าว'))}"
            print("general:", it["title"][:60])
            if post(page_id, token, msg, it["link"]):
                state["posted"].append(it["link"])
                state["last_general"] = now.isoformat()
    if first_run:
        print("first run done")
    save_state(state)


if __name__ == "__main__":
    main()
