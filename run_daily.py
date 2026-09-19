#!/usr/bin/env python3
"""
run_daily.py — 早报流水线编排（机械步骤）。

分两阶段，因为写摘要需要模型（agent），纯脚本做不了：

  阶段A (fetch)   : 抓取 + 处理 → 产出 processed.json + report.txt
                    agent 随后读 processed.json 写 briefing.json
  阶段B (publish) : 校验链接 → 渲染 → git 发布 → 落库去重 → 发飞书卡片

用法：
  python3 run_daily.py fetch [hours]          # 阶段A
  python3 run_daily.py publish [--prod]       # 阶段B（默认 test 仓库/私聊）

cron 唤起的 agent 会话按顺序：run fetch → (agent 写 briefing.json) → run publish。
"""
import subprocess, sys, os, json, datetime, ssl, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TEST = {
    "repo_dir": HERE,
    "pages": "https://endverse.github.io/daily-brief-test",
    "chat_id": "oc_bf5fe15d7eef9babda1d709cc085f641",  # 测试期：私聊
}
PROD = {
    "repo_dir": os.path.expanduser("~/code/endverse/daily-brief"),
    "pages": "https://endverse.github.io/daily-brief",
    "chat_id": None,  # 正式期：用户验收后提供群 ID，再填
}

def run(cmd, **kw):
    print(f"$ {cmd}")
    r = subprocess.run(cmd, shell=True, cwd=HERE, **kw)
    return r.returncode

def stage_fetch(hours):
    if run(f"python3 fetch_sources.py {hours}") != 0:
        sys.exit("抓取失败")
    if run("python3 process_items.py") != 0:
        sys.exit("处理失败")
    print("\n✅ 阶段A 完成。请 agent 读 processed.json + report.txt，撰写 briefing.json，再跑 publish。")

def stage_publish(cfg):
    date = datetime.date.today().isoformat()
    if not os.path.exists(os.path.join(HERE, "briefing.json")):
        sys.exit("缺 briefing.json（需 agent 先写好摘要）")
    # 4. 校验链接
    if run("python3 verify_links.py briefing.json") != 0:
        sys.exit("链接校验未通过，发布中止")
    # 5. 渲染
    if run("python3 render_html.py briefing.json") != 0:
        sys.exit("渲染失败")
    html = f"{date}.html"
    # index.html 指向当天
    with open(os.path.join(HERE, "index.html"), "w") as f:
        f.write(f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
                f'<meta name="viewport" content="width=device-width, initial-scale=1">'
                f'<title>AI & 基础设施早报</title>'
                f'<meta http-equiv="refresh" content="0; url=./{html}">'
                f'<style>body{{font-family:-apple-system,"PingFang SC",sans-serif;background:#e9e2d6;'
                f'color:#15130f;text-align:center;padding:60px 20px}}a{{color:#d7382f}}</style></head>'
                f'<body><p>正在打开最新一期早报…</p><p><a href="./{html}">点此进入 →</a></p></body></html>')
    # 6. 发布
    run(f'git -C "{cfg["repo_dir"]}" add {html} index.html')
    msg = f"Publish {date} briefing"
    subprocess.run(["git","-C",cfg["repo_dir"],"commit","-m",msg])
    run(f'git -C "{cfg["repo_dir"]}" push')
    # 校验线上==本地
    _verify_online(cfg["pages"], html, os.path.join(HERE, html))
    # 7. 落库去重
    run("python3 dedup_history.py commit briefing.json")
    print(f"\n✅ 阶段B 完成。页面: {cfg['pages']}/{html}")
    print("   卡片推送：由 agent 按 SKILL.md『Feishu Card』小节构造并发送（含封面上传/dry-run）。")

def _verify_online(pages, html, local_path):
    import hashlib, time
    ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    local = hashlib.sha256(open(local_path,"rb").read()).hexdigest()
    for i in range(6):
        try:
            req = urllib.request.Request(f"{pages}/{html}", headers={"User-Agent":"Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=15, context=ctx).read()
            if hashlib.sha256(data).hexdigest() == local:
                print(f"✅ 线上 == 本地 ({html})"); return
        except Exception: pass
        time.sleep(12)
    print("⚠️ 线上尚未与本地一致（Pages 可能还在构建），稍后复查。")

if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "fetch"
    if action == "fetch":
        hours = int(sys.argv[2]) if len(sys.argv) > 2 else 24
        stage_fetch(hours)
    elif action == "publish":
        cfg = PROD if "--prod" in sys.argv else TEST
        if cfg["chat_id"] is None and "--prod" in sys.argv:
            print("⚠️ 正式期 chat_id 未配置（等用户提供群 ID）。仅发布网页，跳过卡片。")
        stage_publish(cfg)
    else:
        sys.exit("用法: run_daily.py fetch [hours] | publish [--prod]")
