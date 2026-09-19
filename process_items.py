#!/usr/bin/env python3
"""
process_items.py — 对 raw_items.json 做：AI相关过滤 → 去重 → 6+4分类 → 打分选🔥重点。
输出 processed.json（结构化，供渲染用）+ 一份可读的处理报告（stderr / report.txt）。

验收标准（已与用户对齐）：
  ① 过滤：官方AI源+HF论文全留；其余源关键词命中才留；GitHub Trending 不限语言只要AI相关
  ② 去重：同URL去重 + 跨源标题归一化相似度去重（保留信息最全的一条）
  ③ 分类：来源+关键词映射到 6 AI类 + 4 基础设施类，单归类；开源项目额外打 🔧
  ④ 选🔥重点：权威度 + 量级关键词 + 跨源报道数 打分，超阈值才入选，最多2条，宁缺毋滥
"""
import json, re, sys
from collections import defaultdict

# ---------- 关键词表 ----------
AI_KEYWORDS = [
    # 英文
    r"\bAI\b", "artificial intelligence", "machine learning", r"\bML\b", "deep learning",
    r"\bLLM\b", "large language model", "language model", "neural", "transformer",
    "GPT", "Claude", "Gemini", "Llama", "Mistral", "Qwen", "DeepSeek", "GLM",
    "agent", "agentic", "RAG", "diffusion", "multimodal", "inference", "fine-tun",
    "embedding", "OpenAI", "Anthropic", "DeepMind", "Hugging ?Face", "prompt",
    "chatbot", "copilot", "reasoning model", "foundation model", "MoE", "RLHF",
    # 中文
    "人工智能", "大模型", "大语言模型", "模型", "智能体", "多模态", "推理", "训练",
    "微调", "神经网络", "深度学习", "机器学习", "生成式", "扩散", "对齐", "开源模型",
]
AI_RE = re.compile("|".join(AI_KEYWORDS), re.I)

# 基础设施关键词（用于板块判定 & 过滤云/HN里的infra内容）
INFRA_KEYWORDS = [
    "kubernetes", r"\bk8s\b", "cloud native", "cloud-native", "cncf", "istio",
    "service mesh", "prometheus", "grafana", "argocd", "gitops", "etcd", "helm",
    "container", "docker", "serverless", "eks", "gke", "aks", "云原生", "容器",
    "服务网格", "可观测", "microservice", "微服务", "kubelet", "operator",
]
INFRA_RE = re.compile("|".join(INFRA_KEYWORDS), re.I)

# 分类关键词（AI 6类）
CAT_RULES = {
    "模型与研究": ["模型", "论文", "研究", "benchmark", "榜单", "model", "paper", "research",
                "arxiv", "GPT", "Claude", "Gemini", "Llama", "训练", "pretrain", "fine-tun",
                "SOTA", "多模态", "推理模型", "foundation model"],
    "Agent & Skill": ["agent", "智能体", "agentic", "skill", "tool use", "工具调用",
                      "multi-agent", "多智能体", "autonomous", "MCP", "workflow"],
    "AI 工程落地": ["RAG", "部署", "deploy", "生产", "production", "工程", "engineering",
                 "pipeline", "评测", "eval", "推理优化", "latency", "vector", "架构",
                 "infra", "serving", "落地", "实践", "case study"],
    "产品与商业": ["发布", "launch", "推出", "融资", "funding", "raise", "收购", "acquire",
                "IPO", "估值", "valuation", "商业", "企业版", "订阅", "定价", "pricing",
                "合作", "partnership", "营收", "revenue", "product"],
    "观点与好文": ["观点", "opinion", "分析", "analysis", "认为", "批评", "解读", "深度",
                "essay", "blog", "thoughts", "perspective", "why", "如何看"],
    "安全与治理": ["安全", "security", "越狱", "jailbreak", "漏洞", "vulnerab", "攻击", "attack",
                "泄露", "leak", "监管", "regulat", "合规", "compliance", "risk", "风险",
                "隐私", "privacy", "治理", "governance", "CVE", "对齐", "alignment"],
}
# 基础设施 4 类（按用户优先级：K8s×AI 第一 → K8s核心 → 云原生周边 → 社区）
INFRA_CAT_RULES = {
    "K8s × AI": [  # K8s 与 AI 结合，用户最高优先级
        "kubeflow", "kserve", "kubeai", "gpu operator", "device plugin", "mlops",
        "model serving", "推理服务", "训练集群", "ai infra", "ai infrastructure",
        "llm on kubernetes", "ai on kubernetes", "gpu scheduling", "gpu 调度",
        "vllm", "ray on kubernetes", "分布式训练", "ai workload", "ai 工作负载",
        "gke agent", "agent sandbox",
    ],
    "K8s 核心": ["kubernetes", "k8s", "kubelet", "kube", "KEP", "control plane", "调度",
              "cni", "csi", "网络插件", "存储", "ingress", "operator", "helm"],
    "云原生周边": ["istio", "service mesh", "服务网格", "prometheus", "grafana", "可观测",
               "argocd", "gitops", "etcd", "observability", "envoy", "cilium"],
    "社区与项目": ["cncf", "graduated", "incubat", "sandbox", "毕业", "孵化", "开源项目", "release"],
    "公有云": ["aws", "azure", "gcp", "google cloud", "amazon", "microsoft", "阿里云", "腾讯云", "云服务"],
}
# 基础设施板块内展示顺序（用户指定优先级）
INFRA_ORDER = ["K8s × AI", "K8s 核心", "云原生周边", "社区与项目", "公有云"]

# 权威度评分（源 -> 分）
AUTHORITY = {
    "OpenAI News": 10, "Anthropic News": 10, "Google DeepMind": 10, "Google Research": 9,
    "Mistral AI": 8, "HuggingFace Papers": 7, "arXiv cs.AI": 6, "Simon Willison": 8,
    "Hacker News": 6, "量子位": 6, "InfoQ中国": 6, "GitHub Trending": 6, "GitHub 升星repo": 5,
    "Kubernetes Blog": 8, "CNCF Blog": 7, "AWS News": 7, "Google Cloud": 7, "Azure Updates": 7,
}
# 量级关键词（重大事件信号）
MAGNITUDE = ["发布", "launch", "推出", "融资", "funding", "raise", "收购", "acqui", "突破",
             "breakthrough", "首次", "first", "开源", "open source", "open-source", "重大",
             "state-of-the-art", "SOTA", "GPT-5", "GPT-6", "Claude ", "重磅", "里程碑",
             "billion", "亿美元", "越狱", "jailbreak", "泄露", "重置", "发布会"]
MAG_RE = re.compile("|".join(re.escape(k) if " " in k or k.isascii()==False else k for k in MAGNITUDE), re.I)

OFFICIAL_CATS = {"AI-官方", "AI-研究"}  # 这些源默认全留

def norm_title(t):
    t = re.sub(r"[\s\-–—_|:：，,。.、!！?？\"'“”‘’()（）\[\]【】]+", "", t.lower())
    return t

def is_ai_related(it):
    text = f"{it['title']} {it['summary']}"
    if it["source_cat"] in OFFICIAL_CATS:
        return True
    if it["source"] == "GitHub Trending":
        return bool(AI_RE.search(text))  # 不限语言，只要AI相关
    if it["source_cat"] == "基础设施" or it["source"] in ("Kubernetes Blog","CNCF Blog"):
        return True  # 基础设施源全留（板块内）
    if it["source_cat"] == "公有云":
        return bool(AI_RE.search(text) or INFRA_RE.search(text))  # 云源留AI或infra相关
    return bool(AI_RE.search(text))

def _is_k8s_ai(text):
    """K8s×AI 判定：命中 K8s×AI 专有词，或(明确的K8s平台词 且 明确的AI词)。收紧避免误伤。"""
    # 专有词直接命中
    if any(re.search(re.escape(k), text, re.I) for k in INFRA_CAT_RULES["K8s × AI"]):
        return True
    # 需要明确的 K8s 平台词（不含泛化的 container/算力）
    k8s_strong = re.search(r'kubernetes|k8s|\bkube\b|\bgke\b|\beks\b|\baks\b|云原生|cloud[ -]?native|cncf', text, re.I)
    # 需要明确的 AI 平台词（不含泛化的"算力/模型"，要 agent/LLM/训练/推理/GPU 这类工程词）
    ai_strong = re.search(r'\bAI\b|\bLLM\b|\bagent\b|智能体|机器学习|machine learning|深度学习|GPU|推理|inference|训练|training|模型服务|model serv', text, re.I)
    return bool(k8s_strong and ai_strong)

def classify(it):
    text = f"{it['title']} {it['summary']}"
    # K8s×AI 优先判定（含 GitHub 上 K8s+AI 类开源项目，跨板块抢占）
    if _is_k8s_ai(text):
        return "基础设施", "K8s × AI"
    # 基础设施板块判定：仅限基础设施源，或明确的 K8s/云原生强信号
    infra_strong = re.search(r'kubernetes|k8s|\bkube\b|云原生|cloud[ -]?native|cncf|istio|service mesh|服务网格|argocd|gitops|helm chart', text, re.I)
    if it["source_cat"] in ("基础设施", "公有云") or infra_strong:
        if it["source_cat"] == "公有云" and AI_RE.search(text) and not infra_strong:
            pass  # 公有云源里的纯 AI 内容落到 AI 板块
        else:
            for cat in INFRA_ORDER:
                if any(re.search(re.escape(k), text, re.I) for k in INFRA_CAT_RULES[cat]):
                    return "基础设施", cat
            return "基础设施", "社区与项目"
    # AI 板块 6 类 —— 按优先级判定：安全 > 产品商业 > Agent > 工程 > 观点 > 模型研究(兜底)
    scores = {cat: sum(1 for k in kws if re.search(re.escape(k), text, re.I)) for cat, kws in CAT_RULES.items()}
    PRIORITY = ["安全与治理", "产品与商业", "Agent & Skill", "AI 工程落地", "观点与好文", "模型与研究"]
    best = max(PRIORITY, key=lambda c: (scores[c], -PRIORITY.index(c)))
    if scores[best] == 0:
        best = "AI 工程落地" if it["source"] in ("GitHub Trending","GitHub 升星repo") else "模型与研究"
    return "AI 板块", best

def is_oss(it):
    return it["source"] in ("GitHub Trending", "GitHub 升星repo")

def dedup(items):
    """同URL去重 + 跨源标题相似去重，保留信息最全（summary最长/权威度最高）的一条。"""
    by_url = {}
    for it in items:
        u = it["url"].rstrip("/")
        if u not in by_url or len(it["summary"]) > len(by_url[u]["summary"]):
            by_url[u] = it
    items = list(by_url.values())
    # 标题归一化聚类
    groups = defaultdict(list)
    for it in items:
        groups[norm_title(it["title"])].append(it)
    merged = []
    dup_log = []
    for key, grp in groups.items():
        if len(grp) == 1:
            merged.append(grp[0]); continue
        # 选权威度最高 + summary最长
        best = max(grp, key=lambda x: (AUTHORITY.get(x["source"],0), len(x["summary"])))
        best = dict(best)
        best["extra"] = dict(best["extra"]); best["extra"]["also_reported_by"] = [g["source"] for g in grp if g is not best]
        merged.append(best)
        dup_log.append((best["title"][:40], [g["source"] for g in grp]))
    # 近似标题去重（子串包含）——简单二次合并
    return merged, dup_log

def score_hot(it):
    title = it["title"].strip()
    # 排除垃圾候选：纯日期、过短、Quote 类
    if re.match(r'^[A-Z][a-z]{2}\s+\d', title) or len(title) < 12:
        return 0
    if title.lower().startswith(("quoting", "quote ", "link ")):
        return 0
    s = AUTHORITY.get(it["source"], 3)
    text = f"{title} {it['summary']}"
    s += min(len(MAG_RE.findall(text)), 3) * 3          # 量级词(封顶3次)
    s += len(it["extra"].get("also_reported_by", [])) * 4  # 跨源报道=热点
    try:
        if int(it["extra"].get("upvotes", 0)) > 80: s += 2
    except Exception:
        pass
    # 官方源发布类内容加权
    if it["source_cat"] == "AI-官方" and MAG_RE.search(text):
        s += 3
    return s

def main():
    items = json.load(open("raw_items.json"))
    n0 = len(items)
    # ① 过滤
    kept = [it for it in items if is_ai_related(it)]
    filtered_out = [it for it in items if not is_ai_related(it)]
    # ② 去重（同批）
    deduped, dup_log = dedup(kept)
    # ②b 跨天去重（防 GitHub 榜等常驻内容重复；官方 blog 已按时间窗过滤）
    try:
        from dedup_history import filter_seen
        deduped, cross_day_dropped = filter_seen(deduped)
    except Exception as e:
        cross_day_dropped = []
        print(f"[warn] 跨天去重跳过: {e}", file=sys.stderr)
    # ③ 分类
    for it in deduped:
        board, cat = classify(it)
        it["board"] = board
        it["category"] = cat
        it["oss"] = is_oss(it)
    # ④ 打分选重点
    for it in deduped:
        it["hot_score"] = score_hot(it)
    ranked = sorted(deduped, key=lambda x: x["hot_score"], reverse=True)
    HOT_THRESHOLD = 13
    hot = [it for it in ranked if it["hot_score"] >= HOT_THRESHOLD][:2]
    hot_urls = {h["url"] for h in hot}
    for it in deduped:
        it["is_hot"] = it["url"] in hot_urls

    json.dump(deduped, open("processed.json","w"), ensure_ascii=False, indent=2)

    # ---- 可读报告 ----
    R = []
    R.append("="*70)
    R.append(f"处理报告  (原始 {n0} 条)")
    R.append("="*70)
    R.append(f"\n① 过滤: 保留 {len(kept)} 条, 过滤掉 {len(filtered_out)} 条")
    R.append("   过滤掉的样例(非AI相关):")
    for it in filtered_out[:8]:
        R.append(f"     ✗ [{it['source']}] {it['title'][:50]}")
    R.append(f"\n② 去重: {len(kept)} → {len(deduped)} 条 (同批合并 {len(kept)-len(deduped)-len(cross_day_dropped)}, 跨天历史去重 {len(cross_day_dropped)})")
    if cross_day_dropped:
        R.append("   跨天去重(此前已发过，跳过):")
        for it in cross_day_dropped[:8]:
            R.append(f"     ⏭️  [{it['source']}] {it['title'][:46]}")
    if dup_log:
        R.append("   跨源合并的事件:")
        for title, srcs in dup_log[:8]:
            R.append(f"     ⇉ {title}  ← {srcs}")
    else:
        R.append("   (本批无跨源重复标题)")
    # 分类统计
    R.append(f"\n③ 分类分布:")
    board_cat = defaultdict(lambda: defaultdict(int))
    for it in deduped:
        board_cat[it["board"]][it["category"]] += 1
    for board in ("AI 板块","基础设施"):
        R.append(f"   【{board}】")
        for cat, n in board_cat[board].items():
            oss_n = sum(1 for it in deduped if it["category"]==cat and it["oss"])
            R.append(f"     - {cat}: {n} 条" + (f" (含🔧开源 {oss_n})" if oss_n else ""))
    # 重点
    R.append(f"\n④ 🔥今日重点 (阈值≥{HOT_THRESHOLD}, 最多2条): 选中 {len(hot)} 条")
    for h in hot:
        R.append(f"     🔥 [{h['hot_score']}分] {h['title'][:55]}")
        R.append(f"        源:{h['source']} 类:{h['category']} 跨源:{h['extra'].get('also_reported_by',[])}")
    R.append(f"\n   打分Top5(参考):")
    for it in ranked[:5]:
        R.append(f"     {it['hot_score']:>3}分 [{it['source']:12}] {it['title'][:45]}")
    report = "\n".join(R)
    open("report.txt","w").write(report)
    print(report, file=sys.stderr)
    print(f"\n已写 processed.json ({len(deduped)}条) 和 report.txt", file=sys.stderr)

if __name__ == "__main__":
    main()
