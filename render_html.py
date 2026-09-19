#!/usr/bin/env python3
"""
render_html.py — 把带摘要的结构化数据渲染成杂志风早报 HTML（复用冻结模板样式）。

输入 briefing.json 结构:
{
  "date": "2026-09-19", "weekday": "星期六", "issue": 1,
  "lead": "今日一句话综述...",
  "hot": [ {"title","url","summary","why"} ],          # 0-2 条今日重点
  "boards": {
    "AI 板块": {
      "模型与研究": [ {"title","url","summary","tag","source","oss":false} ],
      ...
    },
    "基础设施": { "K8s 核心": [...], ... }
  },
  "flash": [ {"title","url"} ]                          # 快讯速览
}

样式与 ~/.hermes/skills/daily-brief/templates/template.html 完全一致（FROZEN）。
"""
import json, html, sys, datetime

AI_CATS = [("🧠","模型与研究","Models & Research"),("🧩","Agent & Skill","Agents & Skills"),
           ("🛠️","AI 工程落地","Engineering"),("📊","产品与商业","Product & Biz"),
           ("💡","观点与好文","Opinion"),("🛡️","安全与治理","Safety")]
INFRA_CATS = [("🤖☸️","K8s × AI","K8s × AI"),("☸️","K8s 核心","Kubernetes"),
              ("🌐","云原生周边","Cloud Native"),("📦","社区与项目","Community"),
              ("☁️","公有云","Public Cloud")]

STYLE = """  :root{
    --ink:#15130f; --paper:#e9e2d6; --red:#d7382f; --sub:#6d6459;
    --line:#c9bfae; --card:#f3eee3; --tagbg:#e4dccc;
  }
  *{margin:0;padding:0;box-sizing:border-box;-webkit-text-size-adjust:100%}
  html,body{background:#d8cfbe}
  body{color:var(--ink);font-family:"Noto Serif SC","Songti SC",SimSun,serif;
    line-height:1.8;font-size:16px;
    background:radial-gradient(circle at 30% 12%, rgba(255,255,255,.28), transparent 30%),
      linear-gradient(135deg, rgba(21,19,15,.035) 0 1px, transparent 1px 8px),var(--paper);
    padding:0 0 70px;}
  .paper{max-width:680px;margin:0 auto;
    background:radial-gradient(circle at 70% 8%, rgba(255,255,255,.22), transparent 34%),var(--paper);
    box-shadow:0 0 40px rgba(21,19,15,.12);min-height:100vh}
  .masthead{padding:30px 28px 22px;border-bottom:3px double var(--ink)}
  .brandbar{display:flex;justify-content:space-between;align-items:center;
    font-size:12px;letter-spacing:2px;color:var(--sub);text-transform:uppercase}
  .issue-badge{background:var(--red);color:#fff;padding:3px 10px;font-weight:700;
    letter-spacing:1px;border-radius:2px}
  .title{font-size:46px;font-weight:900;letter-spacing:3px;line-height:1.15;margin:14px 0 6px;text-align:center}
  .title .amp{color:var(--red)}
  .dateline{text-align:center;font-size:13px;letter-spacing:4px;color:var(--sub);
    display:flex;align-items:center;justify-content:center;gap:12px}
  .dateline::before,.dateline::after{content:"";height:1px;width:40px;background:var(--line)}
  .lead{padding:20px 28px;font-size:15px;color:#3a352d;border-bottom:1px dashed var(--line);position:relative}
  .lead .q{font-size:52px;color:var(--red);font-weight:900;line-height:0;
    position:relative;top:14px;margin-right:4px;font-family:Georgia,serif}
  .hot{padding:24px 28px;border-bottom:1px dashed var(--line);
    background:linear-gradient(180deg,rgba(215,56,47,.05),transparent)}
  .hot-kicker{display:inline-block;background:var(--ink);color:var(--paper);
    font-size:12px;letter-spacing:3px;padding:4px 12px;font-weight:700;margin-bottom:14px}
  .hot h2{font-size:26px;font-weight:900;line-height:1.35;margin-bottom:10px}
  .hot h2 a{color:var(--ink);text-decoration:none;border-bottom:3px solid var(--red)}
  .hot p{font-size:15px;color:#3a352d;margin-bottom:8px}
  .hot .why{font-size:14px;color:var(--sub);border-left:3px solid var(--red);padding-left:12px;margin-top:10px}
  .section{padding:22px 28px 6px}
  .sec-head{display:flex;align-items:baseline;gap:10px;margin-bottom:4px;
    border-bottom:2px solid var(--ink);padding-bottom:6px}
  .sec-emoji{font-size:20px}
  .sec-title{font-size:21px;font-weight:900;letter-spacing:1px}
  .sec-en{margin-left:auto;font-size:11px;letter-spacing:2px;color:var(--sub);text-transform:uppercase}
  .board-label{text-align:center;font-size:13px;letter-spacing:6px;color:var(--red);
    font-weight:700;padding:26px 0 4px;text-transform:uppercase}
  .board-label span{border-bottom:2px solid var(--red);padding-bottom:4px}
  .item{padding:15px 0;border-bottom:1px dashed var(--line);display:flex;gap:14px}
  .item:last-child{border-bottom:none}
  .num{font-size:22px;font-weight:900;color:var(--red);line-height:1.2;min-width:30px;font-family:Georgia,serif}
  .item-body{flex:1}
  .item h3{font-size:17px;font-weight:700;line-height:1.5;margin-bottom:5px}
  .item h3 a{color:var(--ink);text-decoration:none}
  .item h3 a:hover{color:var(--red)}
  .item p{font-size:14.5px;color:#4a453c;margin-bottom:8px}
  .meta{font-size:12px;color:var(--sub);display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .tag{background:var(--tagbg);color:#6a5f4d;padding:2px 9px;border-radius:2px;font-size:11px;letter-spacing:1px}
  .tag.oss{background:#dfe8d8;color:#4a6b3a}
  .src{color:var(--red);text-decoration:none;font-weight:500}
  .src::after{content:" ↗";font-size:10px}
  .flash{padding:20px 28px}
  .flash-title{font-size:15px;font-weight:900;letter-spacing:2px;margin-bottom:10px;color:var(--sub)}
  .flash ul{list-style:none}
  .flash li{font-size:14px;padding:7px 0;border-bottom:1px dotted var(--line);display:flex;gap:8px}
  .flash li::before{content:"▪";color:var(--red);flex-shrink:0}
  .flash li a{color:var(--ink);text-decoration:none}
  .flash li a:hover{color:var(--red);text-decoration:underline}
  .footer{padding:28px;text-align:center;border-top:3px double var(--ink);margin-top:14px}
  .footer .logo{font-size:18px;font-weight:900;letter-spacing:2px;margin-bottom:6px}
  .footer .logo .amp{color:var(--red)}
  .footer p{font-size:12px;color:var(--sub);letter-spacing:1px;line-height:1.9}
  @media (max-width:480px){.title{font-size:36px}.hot h2{font-size:22px}
    .section,.masthead,.lead,.hot,.flash{padding-left:20px;padding-right:20px}}"""

def esc(s): return html.escape(s or "", quote=True)

def render_item(n, it):
    tag = esc(it.get("tag","")); oss = it.get("oss")
    tags = ""
    if oss: tags += '<span class="tag oss">🔧 开源</span>'
    if tag: tags += f'<span class="tag">{tag}</span>'
    src = esc(it.get("source",""))
    return f"""    <div class="item">
      <div class="num">{n:02d}</div>
      <div class="item-body">
        <h3><a href="{esc(it['url'])}" target="_blank" rel="noopener">{esc(it['title'])}</a></h3>
        <p>{esc(it.get('summary',''))}</p>
        <div class="meta">{tags}<a class="src" href="{esc(it['url'])}" target="_blank" rel="noopener">{src}</a></div>
      </div>
    </div>"""

def render(data):
    d = data
    parts = []
    parts.append(f"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>AI &amp; 基础设施早报 · {d['date']}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;500;700;900&display=swap" rel="stylesheet">
<style>
{STYLE}
</style>
</head>
<body>
<div class="paper">
  <header class="masthead">
    <div class="brandbar"><span>DAILY BRIEFING</span><span class="issue-badge">第 {d['issue']:03d} 期</span></div>
    <h1 class="title">AI <span class="amp">&amp;</span> 基础设施早报</h1>
    <div class="dateline">{d['date_cn']} · {d['weekday']}</div>
  </header>
  <div class="lead"><span class="q">“</span>{esc(d['lead'])}</div>""")

    # 今日重点
    for h in d.get("hot", []):
        parts.append(f"""  <div class="hot">
    <span class="hot-kicker">🔥 今日重点</span>
    <h2><a href="{esc(h['url'])}" target="_blank" rel="noopener">{esc(h['title'])}</a></h2>
    <p>{esc(h.get('summary',''))}</p>
    <div class="why"><b>新闻要点：</b>{esc(h.get('why',''))}</div>
  </div>""")

    # AI 板块
    ai = d["boards"].get("AI 板块", {})
    if any(ai.get(c[1]) for c in AI_CATS):
        parts.append('  <div class="board-label"><span>🤖 AI 板 块</span></div>')
        n = 1
        for emoji, cat, en in AI_CATS:
            items = ai.get(cat, [])
            if not items: continue
            parts.append(f'''  <section class="section">
    <div class="sec-head"><span class="sec-emoji">{emoji}</span><span class="sec-title">{cat}</span><span class="sec-en">{en}</span></div>''')
            for it in items:
                parts.append(render_item(n, it)); n += 1
            parts.append('  </section>')

    # 基础设施板块
    infra = d["boards"].get("基础设施", {})
    if any(infra.get(c[1]) for c in INFRA_CATS):
        parts.append('  <div class="board-label"><span>☸️ 基础设施板块</span></div>')
        n = 1
        for emoji, cat, en in INFRA_CATS:
            items = infra.get(cat, [])
            if not items: continue
            parts.append(f'''  <section class="section">
    <div class="sec-head"><span class="sec-emoji">{emoji}</span><span class="sec-title">{cat}</span><span class="sec-en">{en}</span></div>''')
            for it in items:
                parts.append(render_item(n, it)); n += 1
            parts.append('  </section>')

    # 快讯
    if d.get("flash"):
        parts.append('  <div class="flash">\n    <div class="flash-title">⚡ 快讯速览</div>\n    <ul>')
        for f in d["flash"]:
            parts.append(f'      <li><a href="{esc(f["url"])}" target="_blank" rel="noopener">{esc(f["title"])}</a></li>')
        parts.append('    </ul>\n  </div>')

    parts.append("""  <footer class="footer">
    <div class="logo">AI <span class="amp">&amp;</span> 基础设施早报</div>
    <p>由 Hermes 自动汇编 · 每日 09:00 更新</p>
  </footer>
</div>
</body>
</html>""")
    return "\n".join(parts)

if __name__ == "__main__":
    infile = sys.argv[1] if len(sys.argv) > 1 else "briefing.json"
    data = json.load(open(infile))
    out = data["date"] + ".html"
    open(out, "w").write(render(data))
    print(f"已渲染 {out}")
