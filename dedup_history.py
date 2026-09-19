#!/usr/bin/env python3
"""
dedup_history.py — 跨天去重（防止 GitHub 榜等常驻内容重复发送）。

机制：
  - seen.json 持久化已发送条目的指纹 {fingerprint: {"first_seen": date, "title":...}}。
  - 指纹 = 归一化URL + 归一化标题。GitHub 项目额外用 repo 全名做指纹（同一 repo 只发一次）。
  - filter_seen(items): 过滤掉指纹已存在的条目（即使今天仍在榜首）。
  - commit_seen(items): 把当天真正发布的条目写入 seen.json。
  - GitHub 项目重大更新（star 翻倍 / 大版本）可作为新事件再发（extra.major_update=True 时放行）。
  - 滑动窗口：seen.json 只保留最近 RETAIN_DAYS 天，防止无限膨胀。

用法：
  process_items.py 产出候选后调用 filter_seen 去掉历史重复；
  确认发布后调用 commit_seen 落库。
"""
import json, re, os, sys
from datetime import datetime, timezone, timedelta

SEEN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seen.json")
RETAIN_DAYS = 30

def _norm(s):
    return re.sub(r"[\s\-–—_|:：，,。.、!！?？\"'“”‘’()（）\[\]【】/]+", "", (s or "").lower())

def fingerprint(it):
    url = it.get("url","").rstrip("/").lower()
    # GitHub 项目：用 repo 全名作指纹（github.com/owner/repo），忽略后续路径
    m = re.search(r"github\.com/([^/]+/[^/?#]+)", url)
    if m:
        return "gh:" + m.group(1).lower()
    # 其余：归一化 URL + 归一化标题前 40 字
    return "u:" + url + "|t:" + _norm(it.get("title",""))[:40]

def load_seen():
    if os.path.exists(SEEN_PATH):
        try: return json.load(open(SEEN_PATH))
        except Exception: return {}
    return {}

def save_seen(seen):
    # 滑动窗口清理
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETAIN_DAYS)).date().isoformat()
    seen = {fp: v for fp, v in seen.items() if v.get("first_seen","9999") >= cutoff}
    json.dump(seen, open(SEEN_PATH,"w"), ensure_ascii=False, indent=2)
    return seen

def filter_seen(items):
    """去掉历史已发过的条目；GitHub 重大更新(extra.major_update)放行。返回 (保留, 被过滤)。"""
    seen = load_seen()
    kept, dropped = [], []
    for it in items:
        fp = fingerprint(it)
        if fp in seen and not it.get("extra",{}).get("major_update"):
            dropped.append(it)
        else:
            kept.append(it)
    return kept, dropped

def commit_seen(items):
    """把今天发布的条目写入 seen.json。"""
    seen = load_seen()
    today = datetime.now(timezone.utc).date().isoformat()
    for it in items:
        fp = fingerprint(it)
        if fp not in seen:
            seen[fp] = {"first_seen": today, "title": it.get("title","")[:60]}
    seen = save_seen(seen)
    return len(seen)

if __name__ == "__main__":
    # CLI: python3 dedup_history.py filter processed.json  → 打印去重后统计
    #      python3 dedup_history.py commit briefing_items.json → 落库
    action = sys.argv[1] if len(sys.argv)>1 else "filter"
    path = sys.argv[2] if len(sys.argv)>2 else "processed.json"
    items = json.load(open(path))
    if isinstance(items, dict):  # briefing.json 结构展开
        flat=[]
        # 新 schema (render.py): highlights / sections[].categories[].items / flash
        flat.extend(items.get("highlights",[]))
        for sec in items.get("sections",[]):
            for cat in sec.get("categories",[]):
                flat.extend(cat.get("items",[]))
        # 旧 schema 兼容: hot / boards
        for h in items.get("hot",[]): flat.append(h)
        for b in items.get("boards",{}).values():
            for c in b.values(): flat.extend(c)
        flat.extend(items.get("flash",[]))
        items = flat
    if action == "filter":
        kept, dropped = filter_seen(items)
        print(f"跨天去重：候选 {len(items)} → 保留 {len(kept)}，过滤历史重复 {len(dropped)}")
        for it in dropped[:15]:
            print(f"   ⏭️  已发过: {it.get('title','')[:50]}  ({fingerprint(it)})")
    elif action == "commit":
        n = commit_seen(items)
        print(f"已落库，seen.json 现有 {n} 条指纹（保留最近 {RETAIN_DAYS} 天）")
