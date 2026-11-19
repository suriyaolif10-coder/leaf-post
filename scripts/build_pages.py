"""Write one static page per community story (n/<uid>.html).

Facebook reads the og: tags of a link to build its preview, and it ignores
everything after "#", so each story needs its own page to show its own
photo and headline when shared.
"""
import html
import json
import os
import re

SITE = os.environ.get("SITE_URL", "https://suriyaolif10-coder.github.io/leaf-post/")

TEMPLATE = """<!doctype html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>{title} | ลีฟโพสต์</title>
<meta name="description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="ลีฟโพสต์ LEAF POST">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{url}">
{og_image}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../logo.png">
<style>
:root{{--bg:#fff;--fg:#111;--muted:#6b6b70;--line:#e6e6e8;--accent:#cc0000}}
@media (prefers-color-scheme:dark){{:root{{--bg:#111;--fg:#f2f2f2;--muted:#9a9aa0;--line:#2a2a2e;--accent:#ff2a2a}}}}
body{{margin:0;background:var(--bg);color:var(--fg);font-family:"Noto Sans Thai",system-ui,sans-serif}}
.wrap{{max-width:720px;margin:0 auto}}
.bar{{display:flex;align-items:center;gap:10px;padding:10px 16px;border-bottom:1px solid var(--line)}}
.bar img{{width:34px;height:34px;border-radius:8px}}
.bar a{{color:inherit;text-decoration:none;font-weight:800;font-size:18px;display:flex;align-items:center;gap:10px}}
.pics img{{display:block;width:100%;height:auto;margin-bottom:6px}}
h1{{font-size:24px;line-height:1.45;margin:14px 16px 6px}}
.m{{color:var(--muted);font-size:14px;margin:0 16px 14px}}
.body{{font-size:18px;line-height:1.8;margin:0 16px;white-space:pre-line;overflow-wrap:anywhere}}
.more{{display:block;margin:28px 16px 40px;padding:14px;text-align:center;border-radius:24px;background:var(--accent);color:#fff;font-weight:700;text-decoration:none}}
.src{{display:inline-block;margin:16px 16px 0;color:var(--accent);font-weight:700}}
</style>
</head>
<body>
<div class="wrap">
<div class="bar"><a href="../"><img src="../logo.png" alt="">ลีฟโพสต์ • ข่าวชุมชน</a></div>
<div class="pics">{cover}</div>
<h1>{title}</h1>
<div class="m">{meta}</div>
<div class="body">{body}</div>
<div class="pics" style="margin-top:16px">{rest}</div>
{src}
<a class="more" href="../">อ่านข่าวอื่นๆ ที่ลีฟโพสต์ ›</a>
</div>
</body>
</html>
"""


def esc(s):
    return html.escape(s or "", quote=True)


def page_url(uid):
    return SITE.rstrip("/") + f"/n/{uid}.html"


def main():
    with open("news.json", encoding="utf-8") as f:
        items = json.load(f).get("items", [])
    os.makedirs("n", exist_ok=True)
    keep = set()
    for it in items:
        uid = it.get("uid")
        if not it.get("own") or not uid or not re.fullmatch(r"c\d+", uid):
            continue
        imgs = it.get("images") or ([it["imageUrl"]] if it.get("imageUrl") else [])
        tags = [f'<img src="{esc(u)}" alt="">' for u in imgs]
        desc = re.sub(r"\s+", " ", it.get("content") or it.get("summary") or "")[:200]
        meta = " • ".join(x for x in [it.get("place"), "ลีฟโพสต์", (it.get("published") or "")[:10]] if x)
        link = it.get("link") or ""
        src = f'<a class="src" href="{esc(link)}" rel="noopener">อ่านข่าวต้นฉบับ ›</a>' if link.startswith("http") and "/issues/" not in link else ""
        page = TEMPLATE.format(
            title=esc(it["title"]), desc=esc(desc), url=esc(page_url(uid)),
            og_image=f'<meta property="og:image" content="{esc(imgs[0])}">' if imgs else '<meta property="og:image" content="../leaf_post_final.png">',
            cover=tags[0] if tags else "", rest="".join(tags[1:]), meta=esc(meta),
            body=esc(it.get("content") or it.get("summary")), src=src)
        name = f"{uid}.html"
        keep.add(name)
        with open(os.path.join("n", name), "w", encoding="utf-8") as f:
            f.write(page)
    for name in os.listdir("n"):
        if name.endswith(".html") and name not in keep:
            os.remove(os.path.join("n", name))  # story was closed/deleted
    print(f"built {len(keep)} community pages")


if __name__ == "__main__":
    main()
