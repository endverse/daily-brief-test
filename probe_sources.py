#!/usr/bin/env python3
"""信息源联通性探测：逐个测试，输出可读报告。不通的标记，不阻塞。"""
import urllib.request, urllib.error, ssl, json, sys
ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE

# (分类, 名称, url, 类型) 类型: rss / json / html
SOURCES = [
  # --- AI 官方博客 ---
  ("AI-官方", "Anthropic (Claude) News", "https://www.anthropic.com/news", "html"),
  ("AI-官方", "OpenAI News", "https://openai.com/news/rss.xml", "rss"),
  ("AI-官方", "Google DeepMind Blog", "https://deepmind.google/blog/rss.xml", "rss"),
  ("AI-官方", "Google Research Blog", "https://research.google/blog/rss/", "rss"),
  ("AI-官方", "Meta AI Blog", "https://ai.meta.com/blog/", "html"),
  ("AI-官方", "Mistral AI News", "https://mistral.ai/rss.xml", "rss"),
  # --- 研究/论文 ---
  ("AI-研究", "HuggingFace Daily Papers", "https://huggingface.co/api/daily_papers", "json"),
  ("AI-研究", "arXiv cs.AI", "http://export.arxiv.org/api/query?search_query=cat:cs.AI&max_results=3&sortBy=submittedDate&sortOrder=descending", "rss"),
  # --- 开源 ---
  ("AI-开源", "GitHub Trending (daily)", "https://github.com/trending?since=daily", "html"),
  ("AI-开源", "GitHub Search 升星快repo", "https://api.github.com/search/repositories?q=AI+created:>2026-09-12&sort=stars&order=desc&per_page=3", "json"),
  # --- 社区/资讯/观点 ---
  ("AI-社区", "Hacker News 高分帖", "https://hnrss.org/frontpage?points=200", "rss"),
  ("AI-社区", "Simon Willison Blog", "https://simonwillison.net/atom/everything/", "rss"),
  # --- 中文 ---
  ("AI-中文", "机器之心", "https://www.jiqizhixin.com/rss", "rss"),
  ("AI-中文", "量子位", "https://www.qbitai.com/feed", "rss"),
  ("AI-中文", "36氪 AI", "https://36kr.com/feed-ai", "rss"),
  ("AI-中文", "InfoQ 中国", "https://www.infoq.cn/feed", "rss"),
  # --- 基础设施 ---
  ("基础设施", "Kubernetes Blog", "https://kubernetes.io/feed.xml", "rss"),
  ("基础设施", "CNCF Blog", "https://www.cncf.io/blog/feed/", "rss"),
  # --- 公有云 ---
  ("公有云", "AWS News Blog", "https://aws.amazon.com/blogs/aws/feed/", "rss"),
  ("公有云", "Google Cloud Blog", "https://cloudblog.withgoogle.com/rss/", "rss"),
  ("公有云", "Azure Updates", "https://www.microsoft.com/releasecommunications/api/v2/azure/rss", "rss"),
  ("公有云", "阿里云最新动态", "https://www.aliyun.com/feed/", "rss"),
  ("公有云", "腾讯云资讯", "https://cloud.tencent.com/developer/rss", "rss"),
]

def probe(url, typ):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0 (Macintosh)"})
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            raw = r.read(4000)
            status = r.status
            if typ == "json":
                try:
                    j = json.loads(raw.decode("utf-8","replace"))
                    n = len(j) if isinstance(j,list) else len(j.get("items",j.get("data",[]))) if isinstance(j,dict) else 0
                    return status, f"JSON ok (~{n} items in first chunk)"
                except Exception:
                    return status, "JSON parse partial (chunked)"
            elif typ in ("rss",):
                txt = raw.decode("utf-8","replace")
                items = txt.count("<item") + txt.count("<entry")
                if "<rss" in txt or "<feed" in txt or "<?xml" in txt:
                    return status, f"RSS/Atom ok (~{items} entries in first chunk)"
                return status, "200 but not XML — check"
            else:  # html
                return status, "HTML ok (需解析)"
    except urllib.error.HTTPError as e:
        return e.code, f"HTTPError {e.code}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:50]}"

results = []
for cat, name, url, typ in SOURCES:
    code, msg = probe(url, typ)
    ok = code == 200
    results.append((cat, name, ok, code, msg, url, typ))
    mark = "✅" if ok else "❌"
    print(f"{mark} [{cat:6}] {name:28} {msg}")

# 汇总
ok_n = sum(1 for r in results if r[2])
print(f"\n=== 汇总: {ok_n}/{len(results)} 联通 ===")
print("❌ 不通的源(标记跳过):")
for cat,name,ok,code,msg,url,typ in results:
    if not ok:
        print(f"   - [{cat}] {name}: {msg}  ({url})")

# 存 JSON 供后续使用
with open("/Users/endverse/code/endverse/daily-brief-test/sources_probe.json","w") as f:
    json.dump([{"cat":c,"name":n,"ok":o,"code":code,"msg":m,"url":u,"type":t} for c,n,o,code,m,u,t in results], f, ensure_ascii=False, indent=2)
print("\n已保存 sources_probe.json")
