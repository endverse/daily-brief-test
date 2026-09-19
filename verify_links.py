#!/usr/bin/env python3
"""
verify_links.py — 发布前链接校验。
规则：
  - briefing.json 里每条 URL 必须来自 processed.json（抓取源），禁止手写拼接。
  - 逐个 HTTP 检查：404/410 = 死链（必须处理）；403/429 = 反爬（浏览器可访问，放行但标注）。
  - 报告不合规项；有死链或有非抓取源 URL 时以非零码退出，阻断发布。
"""
import json, sys, ssl, urllib.request, urllib.error
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

def collect_urls(brief):
    urls=[]
    # 新 schema (render.py): highlights / sections[].categories[].items / flash
    for h in brief.get("highlights",[]): urls.append(("highlight", h["title"], h["url"]))
    for sec in brief.get("sections",[]):
        label = sec.get("label","")
        for cat in sec.get("categories",[]):
            cname = cat.get("title","")
            for it in cat.get("items",[]): urls.append((f"{label}/{cname}", it["title"], it["url"]))
    # 旧 schema 兼容: hot / boards
    for h in brief.get("hot",[]): urls.append(("hot", h["title"], h["url"]))
    for bname, board in brief.get("boards",{}).items():
        for cat, items in board.items():
            for it in items: urls.append((f"{bname}/{cat}", it["title"], it["url"]))
    for f in brief.get("flash",[]): urls.append(("flash", f["title"], f["url"]))
    return urls

def http_status(u):
    for method in ("HEAD","GET"):
        try:
            req=urllib.request.Request(u, headers={"User-Agent":UA}, method=method)
            r=urllib.request.urlopen(req, timeout=15, context=ctx)
            return r.status
        except urllib.error.HTTPError as e:
            if method=="GET": return e.code
        except Exception as e:
            if method=="GET": return str(e)[:30]
    return None

def main():
    brief = json.load(open(sys.argv[1] if len(sys.argv)>1 else "briefing.json"))
    proc_urls = {it["url"] for it in json.load(open("processed.json"))}
    urls = collect_urls(brief)
    dead, foreign, ok, antibot = [], [], [], []
    for where, title, u in urls:
        # 来源校验：URL 必须来自抓取源
        if u not in proc_urls:
            foreign.append((where, title, u))
        st = http_status(u)
        if st in (404, 410):
            dead.append((where, title, u, st))
        elif st in (403, 429):
            antibot.append((where, title, u, st))
        elif st == 200:
            ok.append(u)
        else:
            dead.append((where, title, u, st))  # 其他异常按需处理
    print(f"链接校验：{len(ok)} OK · {len(antibot)} 反爬(放行) · {len(dead)} 死链 · {len(foreign)} 非抓取源")
    if antibot:
        print("\n⚠️ 反爬(403/429，浏览器可访问，放行):")
        for w,t,u,s in antibot: print(f"   [{s}] {t[:40]}")
    if foreign:
        print("\n❌ 非抓取源 URL(疑似手写拼接，禁止！必须换成 processed.json 里的原始 URL):")
        for w,t,u in foreign: print(f"   [{w}] {t[:40]}\n        {u}")
    if dead:
        print("\n❌ 死链(必须换链接或删除该条):")
        for w,t,u,s in dead: print(f"   [{s}] [{w}] {t[:40]}\n        {u}")
    if dead or foreign:
        print("\n发布被阻断：先修复上述问题。")
        sys.exit(1)
    print("\n✅ 全部通过，可发布。")

if __name__ == "__main__":
    main()
