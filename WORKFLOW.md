# 每日早报 · 完整工作流 (WORKFLOW)

> 一份「AI & 基础设施早报」从抓取到推送的端到端流程。定时任务和 skill 拆分都以此为准。

## 总览

```
每天 09:00 (cron 唤起 agent 会话)
   │
   ├─ 1. 抓取      fetch_sources.py  → raw_items.json
   ├─ 2. 处理      process_items.py  → processed.json + report.txt
   │                (AI过滤 → 同批去重 → 跨天去重 → 6+4分类 → 打分选🔥重点)
   ├─ 3. 撰写摘要   agent 读 processed.json，按摘要铁律写中文摘要 → briefing.json
   ├─ 4. 校验链接   verify_links.py briefing.json   (死链/手写URL 阻断发布)
   ├─ 5. 渲染      render_html.py briefing.json → YYYY-MM-DD.html
   ├─ 6. 发布      git commit + push → GitHub Pages，curl 校验线上==本地
   ├─ 7. 落库去重   dedup_history.py commit briefing.json → 更新 seen.json
   └─ 8. 推送卡片   上传封面 → 构造 Card 2.0(样式A) → lark-cli 发到私聊/群
```

关键点：步骤 3（写摘要）需要「模型」，所以整条流程由 **cron 唤起的 agent 会话**执行，而不是纯脚本 cron。脚本负责机械活（抓取/处理/校验/渲染/发布/落库/发卡），agent 负责选题与写摘要。

## 各步骤明细

### 1. 抓取 `fetch_sources.py [hours]`
- 拉取 19 个一等源过去 N 小时内容（默认 24h；arXiv/低频源可用 72h）。
- 统一结构：`title, url, summary, published, source, source_cat, extra`。
- 只用标准库；RSS/Atom、HF papers JSON、GitHub Trending/Search、Anthropic HTML 各有解析分支。
- 输出 `raw_items.json`。

### 2. 处理 `process_items.py`
- **① AI 过滤**：官方 AI 源 + HF/arXiv 全留；其余源关键词命中才留；GitHub Trending 不限语言只留 AI 相关。
- **② 同批去重**：同 URL + 跨源标题归一化，保留权威度最高/信息最全的一条。
- **②b 跨天去重**：调 `dedup_history.filter_seen`，剔除 seen.json 里已发过的（GitHub 项目按 repo 全名，防霸榜重复）。
- **③ 分类**：K8s×AI 优先判定 → 基础设施(K8s核心/云原生/社区/公有云) → AI 6 类(安全>产品>Agent>工程>观点>模型 优先级)。开源项目打 🔧。
- **④ 打分选🔥重点**：权威度 + 量级词 + 跨源报道数，阈值≥13，最多 2 条，宁缺毋滥。排除纯日期/过短/Quote 类垃圾候选。
- 输出 `processed.json` + 可读 `report.txt`。

### 3. 撰写摘要（agent 手工，产出 briefing.json）
按 SKILL.md「Summary Writing Standard」：
- 默认 2-3 句，信息密度拉满，每条至少一个具体事实。
- **仅 skill/agent 落地实践 / agent 最佳实践类**写详细（4-6 句，含做法/用了什么/解决什么问题）。
- 客观陈述「技术能做什么/解决什么问题」，**禁止**「对做XX的人」「对你意味着」这类回答式表达。
- 🔥今日重点的第二段是 **新闻要点**（客观关键事实），不是「为什么重要」。
- **URL 只能复制 processed.json 里的原始地址，禁止手写拼接。**
- 每类展示 3-5 条；基础设施板块按 K8s×AI → K8s核心 → 云原生 → 社区 → 公有云 顺序。

### 4. 校验链接 `verify_links.py briefing.json`
- 死链(404/410) 或 非抓取源 URL(手写) → 退出码 1，阻断发布。
- 反爬(403/429) → 放行并标注（浏览器可访问）。

### 5. 渲染 `render_html.py briefing.json`
- 用冻结的杂志风模板（样式来自 skill templates/template.html）渲染成 `YYYY-MM-DD.html`。
- 只填内容，`<style>` 逐字不变。

### 6. 发布
- 更新 `index.html` meta-refresh 指向当天文件。
- `git add + commit -F <msg> + push`（英文提交、最小改动拆分）。
- 等 Pages 构建（~1-2 min），`curl` 校验线上 hash == 本地 hash。

### 7. 落库去重 `dedup_history.py commit briefing.json`
- 把当天真正发布的条目指纹写入 seen.json（30 天滑动窗口）。

### 8. 推送飞书卡片（样式A）
- 上传封面 `daily_brief_cover.png` 拿 image_key（key 可能过期，每次重传最稳）。
- Card 2.0：封面图 + header(标题/日期/期号) + 🔥重点 markdown + 今日看点 markdown + 灰字统计 + 主按钮(open_url→当天页) + 灰字页脚。
- `--dry-run` 校验后正式发送到目标 chat。
- 测试期发 daily-brief-test 对应页 + 私聊；正式期发 daily-brief + 指定群。

## 文件清单

| 文件 | 角色 | 是否入库 |
|---|---|---|
| fetch_sources.py | 抓取 | ✅ |
| process_items.py | 过滤/去重/分类/打分 | ✅ |
| dedup_history.py | 跨天去重（seen.json 读写） | ✅ |
| verify_links.py | 发布前链接校验 | ✅ |
| render_html.py | 渲染杂志风 HTML | ✅ |
| SOURCES.md | 信息源清单 | ✅ |
| WORKFLOW.md | 本文件 | ✅ |
| YYYY-MM-DD.html / index.html | 早报产物 | ✅ |
| raw_items.json / processed.json / report.txt / briefing.json | 运行中间产物 | ❌ gitignore |
| seen.json | 去重历史 | ⚠️ 需持久化（见下） |
| cover_upload.png / card_*.json | 卡片临时件 | ❌ gitignore |

> **seen.json 持久化**：跨天去重依赖它长期存在。测试期放在仓库工作目录（可 gitignore 或入库均可，定时任务里保证不被清理即可）；正式期同理。它是唯一必须跨运行保留的状态文件。

## 待接入 / 已知限制
- **X/Twitter**：xurl 已装但未配置 X API 凭据，需用户在开发者后台注册+认证后启用（涉及密钥，agent 不能代做）。
- **机器之心/36氪**：官方 RSS 已停用，降级为 HTML 抓取备选，未纳入一等源。
- **阿里云/腾讯云**：无公开官方 RSS，已丢弃；公有云保留 AWS/GCP/Azure。
