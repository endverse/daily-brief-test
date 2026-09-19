# 信息源联通性测试结果（任务2）

测试时间：2026-09-19。逐个探测，不通的标记跳过、不阻塞后续。

## ✅ 可用源（一等源，RSS/JSON/API，稳定）

### AI 官方博客
- Anthropic (Claude) News — https://www.anthropic.com/news （HTML 抓取）
- OpenAI News — https://openai.com/news/rss.xml （RSS）
- Google DeepMind Blog — https://deepmind.google/blog/rss.xml （RSS）
- Google Research Blog — https://research.google/blog/rss/ （RSS）
- Meta AI Blog — https://ai.meta.com/blog/ （HTML 抓取）
- Mistral AI News — https://mistral.ai/rss.xml （RSS）

### 研究/论文
- HuggingFace Daily Papers — https://huggingface.co/api/daily_papers （JSON API）
- arXiv cs.AI/cs.CL/cs.LG — http://export.arxiv.org/api/query （Atom API，关键词过滤）

### 开源
- GitHub Trending (daily) — https://github.com/trending?since=daily （HTML 抓取，仅取 AI 相关）
- GitHub 升星快 repo — https://api.github.com/search/repositories?q=...created:>近N天&sort=stars （JSON API）

### 社区/观点
- Hacker News 高分帖 — https://hnrss.org/frontpage?points=200 （RSS）
- Simon Willison Blog — https://simonwillison.net/atom/everything/ （Atom）

### 中文
- 量子位 — https://www.qbitai.com/feed （RSS）✅
- InfoQ 中国 — https://www.infoq.cn/feed （RSS）✅

### 基础设施
- Kubernetes Blog — https://kubernetes.io/feed.xml （RSS）
- CNCF Blog — https://www.cncf.io/blog/feed/ （RSS）

### 公有云
- AWS News Blog — https://aws.amazon.com/blogs/aws/feed/ （RSS）✅
- Google Cloud Blog — https://cloudblog.withgoogle.com/rss/ （RSS）✅
- Azure Updates — https://www.microsoft.com/releasecommunications/api/v2/azure/rss （RSS）✅

## ⚠️ 降级为 HTML 抓取备选（官方 RSS 已停用，结构不稳）
- 机器之心 — https://www.jiqizhixin.com/ （RSS 已废弃，需 HTML 解析，二等源）
- 36氪 AI — https://36kr.com/ （RSS 已废弃，需 HTML 解析，二等源）

## ❌ 丢弃（无可用官方源，按用户"厂商RSS无法访问可以不要"）
- 阿里云 — 无公开官方 RSS（404）
- 腾讯云 — 无公开官方 RSS（404）

## ⏸️ 待用户配置（不阻塞）
- X / Twitter（@OpenAIDevs @sama @romainhuet @AnthropicAI @GoogleDeepMind @OpenAI）
  - xurl 已安装，但未注册 X API app / 未认证。需用户在 X 开发者后台注册并手动 auth（涉及密钥，agent 不能代做）。
  - 配置完成前，X 源标记跳过。

## 结论
- 一等源 19 个，覆盖 AI 6 类 + 基础设施 4 类（公有云 3 家）。
- 中文深度源（机器之心/36氪）走 HTML 抓取备选。
- X 待用户配置后接入。
