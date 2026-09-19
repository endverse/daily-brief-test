#!/usr/bin/env python3
"""
fetch_sources.py — 拉取所有信息源过去 N 小时的条目，输出统一结构的 raw items。

统一条目结构 (dict):
  {
    "title": str,
    "url": str,
    "summary": str,        # 原文摘要/描述（可能为空）
    "published": str,      # ISO 时间（尽量解析）
    "source": str,         # 源名称
    "source_cat": str,     # 源大类: AI-官方/AI-研究/AI-开源/AI-社区/AI-中文/基础设施/公有云
    "extra": dict,         # 附加信息（如 github stars）
  }

只依赖标准库（urllib + xml + json + html.parser），无需第三方包。
"""
import urllib.request, urllib.error, urllib.parse, ssl, json, re, sys
from xml.etree import ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

CTX = ssl.create_default_context(); CTX.check_hostname=False; CTX.verify_mode=ssl.CERT_NONE
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
NOW = datetime.now(timezone.utc)

def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return r.read()

def _parse_date(s):
    if not s: return None
    s = s.strip()
    for fn in (parsedate_to_datetime,):
        try:
            d = fn(s)
            if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception: pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%SZ","%Y-%m-%dT%H:%M:%S.%f%z","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
        try:
            d = datetime.strptime(s, fmt)
            if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception: pass
    # arxiv/ISO fallback
    try:
        d = datetime.fromisoformat(s.replace("Z","+00:00"))
        if d.tzinfo is None: d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None

def _clean(txt):
    if not txt: return ""
    txt = re.sub(r"<[^>]+>", "", txt)          # strip tags
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:500]

# ---------- RSS / Atom ----------
def fetch_rss(name, cat, url, hours):
    out = []
    try:
        raw = _get(url)
    except Exception as e:
        return out, f"ERR {type(e).__name__}: {str(e)[:40]}"
    try:
        # strip default namespaces to simplify
        text = raw.decode("utf-8", "replace")
        root = ET.fromstring(re.sub(r'xmlns="[^"]+"', "", text, count=0).encode("utf-8"))
    except Exception as e:
        return out, f"XML parse err: {str(e)[:40]}"
    cutoff = NOW - timedelta(hours=hours)
    # RSS <item> or Atom <entry>
    items = root.findall(".//item") or root.findall(".//entry")
    for it in items:
        title = (it.findtext("title") or "").strip()
        # link: rss text, atom href
        link = (it.findtext("link") or "").strip()
        if not link:
            le = it.find("link")
            if le is not None: link = le.get("href","")
        desc = it.findtext("description") or it.findtext("summary") or it.findtext("content") or ""
        pub = it.findtext("pubDate") or it.findtext("published") or it.findtext("updated") or ""
        d = _parse_date(pub)
        if d and d < cutoff:
            continue
        if not title or not link:
            continue
        out.append({"title": title, "url": link, "summary": _clean(desc),
                    "published": d.isoformat() if d else "", "source": name,
                    "source_cat": cat, "extra": {}})
    return out, f"ok {len(out)} in {hours}h"

# ---------- HuggingFace daily papers ----------
def fetch_hf(name, cat, url, hours):
    out = []
    try:
        j = json.loads(_get(url).decode("utf-8","replace"))
    except Exception as e:
        return out, f"ERR {str(e)[:40]}"
    for p in j[:30]:
        paper = p.get("paper", p)
        title = paper.get("title","").strip()
        pid = paper.get("id","")
        if not title or not pid: continue
        out.append({"title": title, "url": f"https://huggingface.co/papers/{pid}",
                    "summary": _clean(paper.get("summary","")),
                    "published": p.get("publishedAt",""), "source": name,
                    "source_cat": cat, "extra": {"upvotes": paper.get("upvotes",0)}})
    return out, f"ok {len(out)} papers"

# ---------- GitHub search (fast-rising repos) ----------
def fetch_gh_search(name, cat, hours):
    out = []
    days = max(1, hours//24)
    since = (NOW - timedelta(days=max(days,3))).strftime("%Y-%m-%d")
    q = f"created:>{since} sort:stars"
    url = f"https://api.github.com/search/repositories?q={urllib.parse.quote(q)}&sort=stars&order=desc&per_page=20"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept":"application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=20, context=CTX) as r:
            j = json.loads(r.read().decode("utf-8","replace"))
    except Exception as e:
        return out, f"ERR {str(e)[:40]}"
    for repo in j.get("items", []):
        title = repo.get("full_name","")
        desc = repo.get("description","") or ""
        out.append({"title": title, "url": repo.get("html_url",""),
                    "summary": _clean(desc), "published": repo.get("created_at",""),
                    "source": name, "source_cat": cat,
                    "extra": {"stars": repo.get("stargazers_count",0), "lang": repo.get("language","")}})
    return out, f"ok {len(out)} repos"

# ---------- GitHub Trending (HTML) ----------
def fetch_gh_trending(name, cat, hours):
    out = []
    try:
        html = _get("https://github.com/trending?since=daily").decode("utf-8","replace")
    except Exception as e:
        return out, f"ERR {str(e)[:40]}"
    for a in re.findall(r'<article class="Box-row">(.*?)</article>', html, re.S):
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="/([^"/]+)/([^"?]+)"', a, re.S)
        if not m: continue
        full = f"{m.group(1)}/{m.group(2)}"
        dm = re.search(r'<p class="col-9[^"]*"[^>]*>(.*?)</p>', a, re.S)
        desc = _clean(dm.group(1)) if dm else ""
        sm = re.search(r'([\d,]+)\s*stars today', a)
        out.append({"title": full, "url": f"https://github.com/{full}",
                    "summary": desc, "published": NOW.isoformat(), "source": name,
                    "source_cat": cat, "extra": {"trending": True, "stars_today": sm.group(1) if sm else ""}})
    return out, f"ok {len(out)} trending"

# ---------- Anthropic News (HTML list) ----------
def fetch_anthropic(name, cat, url, hours):
    out = []
    try:
        html = _get(url).decode("utf-8","replace")
    except Exception as e:
        return out, f"ERR {str(e)[:40]}"
    seen = set()
    from urllib.parse import urljoin
    for m in re.finditer(r'href="(/news/[^"?#]+)"[^>]*>(.*?)</li>', html, re.S):
        slug = m.group(1)
        if slug in seen: continue
        seen.add(slug)
        raw_inner = m.group(2)
        # 结构化解析：日期在 <time>、分类在 subject span、标题在其后的 title span
        dm = re.search(r'<time[^>]*>([^<]+)</time>', raw_inner)
        date_txt = dm.group(1).strip() if dm else ""
        pub = _parse_date(date_txt) or NOW
        if pub < NOW - timedelta(hours=hours):
            continue
        inner = _clean(raw_inner).replace("&#x27;","'").replace("&#39;","'").replace("&amp;","&")
        # 依次剥掉：日期、分类词
        title = re.sub(r'^[A-Z][a-z]{2}\s+\d{1,2},\s*\d{4}', '', inner).strip()
        title = re.sub(r'^(Announcements|Product|Policy|Research|Interpretability|Societal Impacts|Alignment|Company|Event)', '', title).strip()
        # featured/hero item：标题后仍黏 "On July 30, we..." 正文，截断到第一句
        title = re.sub(r'\s*On\s+[A-Z][a-z]{2,8}\s+\d{1,2}.*$', '', title).strip()
        if len(title) < 8:
            title = slug.rsplit("/",1)[-1].replace("-"," ").strip().capitalize()
        out.append({"title": title[:140], "url": urljoin(url, slug), "summary": "",
                    "published": pub.isoformat(), "source": name, "source_cat": cat, "extra": {}})
    return out, f"ok {len(out)} links (anthropic)"

# ---------- 通用 HTML 链接列表 ----------
def fetch_html_list(name, cat, url, hours, link_re):
    out = []
    try:
        html = _get(url).decode("utf-8","replace")
    except Exception as e:
        return out, f"ERR {str(e)[:40]}"
    seen=set()
    for m in re.finditer(link_re, html):
        href = m.group("href"); title = _clean(m.group("title")) if "title" in m.groupdict() and m.group("title") else ""
        if href in seen: continue
        seen.add(href)
        if href.startswith("/"):
            from urllib.parse import urljoin
            href = urljoin(url, href)
        out.append({"title": title or href, "url": href, "summary": "",
                    "published": NOW.isoformat(), "source": name, "source_cat": cat, "extra": {}})
    return out, f"ok {len(out)} links (html)"

# ---------- 源配置 ----------
def all_sources(hours=24):
    tasks = [
        ("OpenAI News","AI-官方","rss","https://openai.com/news/rss.xml"),
        ("Google DeepMind","AI-官方","rss","https://deepmind.google/blog/rss.xml"),
        ("Google Research","AI-官方","rss","https://research.google/blog/rss/"),
        ("Mistral AI","AI-官方","rss","https://mistral.ai/rss.xml"),
        ("HuggingFace Papers","AI-研究","hf","https://huggingface.co/api/daily_papers"),
        ("arXiv cs.AI","AI-研究","rss","http://export.arxiv.org/api/query?search_query=cat:cs.AI+OR+cat:cs.CL+OR+cat:cs.LG&max_results=40&sortBy=submittedDate&sortOrder=descending"),
        ("GitHub Trending","AI-开源","ghtrend",""),
        ("GitHub 升星repo","AI-开源","ghsearch",""),
        ("Hacker News","AI-社区","rss","https://hnrss.org/frontpage?points=200"),
        ("Simon Willison","AI-社区","rss","https://simonwillison.net/atom/everything/"),
        ("量子位","AI-中文","rss","https://www.qbitai.com/feed"),
        ("InfoQ中国","AI-中文","rss","https://www.infoq.cn/feed"),
        ("Kubernetes Blog","基础设施","rss","https://kubernetes.io/feed.xml"),
        ("CNCF Blog","基础设施","rss","https://www.cncf.io/blog/feed/"),
        ("AWS News","公有云","rss","https://aws.amazon.com/blogs/aws/feed/"),
        ("Google Cloud","公有云","rss","https://cloudblog.withgoogle.com/rss/"),
        ("Azure Updates","公有云","rss","https://www.microsoft.com/releasecommunications/api/v2/azure/rss"),
        ("Anthropic News","AI-官方","anthropic","https://www.anthropic.com/news"),
    ]
    all_items=[]; report=[]
    for name,cat,typ,url in tasks:
        if typ=="rss": items,msg = fetch_rss(name,cat,url,hours)
        elif typ=="hf": items,msg = fetch_hf(name,cat,url,hours)
        elif typ=="ghsearch": items,msg = fetch_gh_search(name,cat,hours)
        elif typ=="ghtrend": items,msg = fetch_gh_trending(name,cat,hours)
        elif typ=="anthropic": items,msg = fetch_anthropic(name,cat,url,hours)
        else: items,msg=[],"skip"
        report.append(f"  [{cat:6}] {name:20} -> {msg}")
        all_items.extend(items)
    return all_items, report

if __name__ == "__main__":
    hours = int(sys.argv[1]) if len(sys.argv)>1 else 24
    items, report = all_sources(hours)
    print("\n".join(report), file=sys.stderr)
    print(f"\n总计抓取 {len(items)} 条 (过去 {hours}h)", file=sys.stderr)
    json.dump(items, open("raw_items.json","w"), ensure_ascii=False, indent=2)
    print("已写 raw_items.json", file=sys.stderr)
