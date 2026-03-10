# 🌐 Lilith Legal · 全球游戏立法动态监控

> 面向中资手游出海合规团队的自动化法规情报工具，持续追踪全球主要市场的游戏监管动态。

---

## 功能概览

- **自动抓取**：从 30+ 个官方监管机构、法律媒体、行业资讯 RSS 源实时获取法规动态；同时通过 Google News 多语言搜索（英、日、韩、越、印尼、德、法、葡、西、泰、阿拉伯语等）覆盖本地语种媒体
- **AI 翻译与提炼**：基于硅基流动 Qwen3-8B 批量处理，将原文转化为规范中文标题和合规摘要；专有名词（Loot Box、GDPR、FTC 等）自动保留英文；每批 3 条并发处理，效率比逐条提升 3 倍
- **噪音过滤**：自动拦截硬件评测（电池技术、芯片架构、Wi-Fi 标准等）、电竞赛事、公司财报、Google/Apple 非合规相关新闻；`impact_score = 0` 的条目不进入任何报告或通知
- **智能分类**：按 5 大显示分组（北美 / 欧洲 / 日韩台 / 亚太区 / 其他）和 9 个合规类别自动归类，信源权威性（官方 > 法律 > 行业 > 媒体）作为展示主排序键
- **四重去重**：URL 精确匹配 → 事件指纹预筛（实体 + 议题匹配）→ Bigram 语义相似度 → LLM 批量核验，跨区域同一事件自动合并，官方来源优先覆盖媒体报道
- **双端 HTML 报告**：生成移动端（`latest-mobile.html`）和 PC 端（`latest-pc.html`）两份报告，均含 LLM 上周动态总结、可交互地区筛选；通过 GitHub Pages 直接分发，加载 < 2 秒
- **飞书通知**：
  - **日报**：有昨日新增动态时推送执行级飞书卡片（**周一至周五**）；按风险分级着色（🔴≥9.0 / 🟠≥7.0 / 🔵其他）；顶部附 AI 生成的 150 字综述；每条动态含机制变动摘要和全平台影响
  - **周报**：团队完成飞书多维表格初筛后手动触发，飞书卡片含区域分布统计 + LLM 综述 + 两个报告直链按钮

---

## 自动化工作流

| 任务 | Workflow 文件 | 触发方式 | 说明 |
|------|--------------|----------|------|
| 每日数据同步 | `daily_check.yml` | 每天 BJT 08:00 自动 | 抓取昨日数据 → AI 翻译分类 → 写入飞书多维表格（每天）→ 推送飞书日报（仅工作日） |
| 发布周报 | `publish_report.yml` | 手动触发 | 从飞书多维表格读取已审条目 → 生成双端 HTML + PDF → 存档 → 发送飞书周报卡片 |

**数据流向**：

```
每天 BJT 08:00
    monitor.py run --period day
        ↓ 抓取 + 翻译 + 分类
    daily_check.py
        ↓ 质量过滤（impact_score > 0 + title_zh 非空）
        ├── 写入飞书多维表格（每天，含周末）
        └── 推送飞书日报卡片（仅周一至周五）

手动触发"发布周报"
    monitor.py report --format html --period week
        ↓ 从飞书多维表格读取已审条目
    reporter.py → latest-mobile.html / latest-pc.html
    generate_pdf.py → 周报.pdf
    feishu_notify.py → 飞书周报卡片
```

---

## 覆盖地区与来源

| 显示分组 | 涵盖地区 | 代表监管来源 |
|----------|----------|-------------|
| 🌎 北美 | 美国、加拿大、墨西哥及中美洲/加勒比海 | FTC、联邦公报、纽约州 AG、加拿大竞争局 |
| 🌍 欧洲 | 欧盟、英国、德国、法国、荷兰、俄罗斯等全欧 | GDPR 执法动态、Ofcom、ICO、CNIL、PEGI |
| 🌸 日韩台 | 日本、韩国、台湾 | GRAC（韩国）、CERO（日本）、台湾数位部 |
| 🇭🇰 港澳 | 香港、澳门 | 香港通讯事务管理局、澳门文化局 |
| 🌏 亚太区 | 越南、印尼、泰国、菲律宾、马来西亚、新加坡等东南亚十一国 | 越南信息通信部、印尼 Kominfo、澳大利亚 eSafety |
| 🌐 其他 | 沙特、阿联酋、印度、巴西、土耳其、南非等 | 沙特通信部、SENACON（巴西）、印度 MeitY |

---

## 合规分类

| 分类 | 典型议题 |
|------|----------|
| 🔒 数据隐私 | GDPR / CCPA 执法、儿童隐私 (COPPA)、跨境数据传输、数据本地化 |
| 🎲 玩法合规 | Loot Box / Gacha 监管、概率公示、虚拟货币、涉赌认定 |
| 🧒 未成年人保护 | 年龄验证、未成年消费限制、游戏时长管控、家长控制 |
| 📣 广告营销合规 | 虚假广告、KOL 披露义务、暗黑模式、价格透明度 |
| 🛡️ 消费者保护 | 退款政策、订阅自动续费、消费者权益诉讼 |
| 🏢 经营合规 | 本地代理 / 代表处、游戏许可证、税务合规、外资限制 |
| 📱 平台政策 | App Store / Google Play 政策、第三方支付、DMA 合规、IAP 规则 |
| 📋 内容监管 | 内容审查、AI 生成内容、版权合规、游戏分级 |
| 💻 PC & 跨平台合规 | PC Launcher 权限、Anti-cheat 合规、D2C 充值、跨平台账号体系 |

---

## 项目架构

```
Monitor/
├── monitor.py          # 主入口：run / report / query / stats / retranslate
├── fetcher.py          # RSS + Google News 多语言抓取，去重写入 DB
├── classifier.py       # 分类打标（地区 / 类别 / 状态 / 影响分值 / 信源层级）
├── translator.py       # AI 批量翻译 + 术语修正 + LLM 重复对核验 + 摘要融合 + 综述生成
├── reporter.py         # 双端 HTML 报告生成（移动端 + PC 端，含事件指纹去重、信源排序）
├── models.py           # 数据模型（LegislationItem）+ SQLite 数据库操作
├── config.py           # 搜索关键词库、RSS 源、分类标签、输出配置
├── utils.py            # 共享工具：区域分组映射、send_card、bigram 去重、tier 排序等
├── daily_check.py      # 日报脚本：查询昨日新增 → 写入 Bitable → 推送飞书（工作日）
├── feishu_notify.py    # 周报脚本：查询本周数据 → LLM 综述 → 构建飞书卡片 → 推送
├── feishu_bitable.py   # 飞书多维表格读写（write: daily_check / read: reporter）
├── generate_pdf.py     # Playwright 截图：PC 端 HTML → PDF（含日期范围命名）
├── requirements.txt    # Python 依赖
├── data/
│   └── monitor.db      # SQLite 数据库（法规条目，随 CI 自动提交）
├── reports/
│   ├── latest-mobile.html   # 最新移动端报告（GitHub Pages 分发）
│   ├── latest-pc.html       # 最新 PC 端报告（适合宽屏阅读和 PDF 打印）
│   ├── latest.html          # 移动端别名（向后兼容）
│   └── archive/             # 历史周报（YYYY-WXX/weekly-mobile.html 等）
└── assets/
    ├── lilith-logo.jpg      # 品牌 Logo
    └── fonts/               # 自托管字体（Inter Variable + JetBrains Mono）
```

---

## 一次性部署（GitHub）

### 1. Fork / 克隆本仓库

```bash
git clone https://github.com/evonotevil/Monitor.git
cd Monitor
```

### 2. 配置 GitHub Secrets

在仓库页面进入 **Settings → Secrets and variables → Actions → New repository secret**，添加以下 Secrets：

| Secret 名称 | 说明 | 是否必填 |
|-------------|------|---------|
| `LLM_API_KEY` | 硅基流动 API Key（[免费申请](https://cloud.siliconflow.cn)） | ✅ 必填 |
| `FEISHU_WEBHOOK_URL` | 飞书自定义机器人 Webhook 地址 | ✅ 必填（否则通知不发送） |
| `FEISHU_APP_ID` | 飞书自建应用 App ID | 可选（多维表格写入） |
| `FEISHU_APP_SECRET` | 飞书自建应用 App Secret | 可选（多维表格写入） |
| `FEISHU_BITABLE_APP_TOKEN` | 多维表格 URL 中的 app_token（`BmXXX` 部分） | 可选（多维表格写入） |
| `FEISHU_BITABLE_WIKI_TOKEN` | 多维表格 Wiki token（`wiki/xxx` 部分，如使用知识库） | 可选 |
| `FEISHU_BITABLE_TABLE_ID` | 多维表格 URL 中的 table_id（`tblXXX` 部分） | 可选（多维表格写入） |

### 3. 启用 GitHub Pages

进入 **Settings → Pages**，Source 选择 `Deploy from a branch`，Branch 选 `main`，目录选 `/ (root)`，Save。

报告 URL 格式：
- 移动端：`https://<owner>.github.io/<repo>/reports/latest-mobile.html`
- PC 端：`https://<owner>.github.io/<repo>/reports/latest-pc.html`

---

## 本地调试

```bash
# 安装依赖
pip install -r requirements.txt
playwright install chromium      # 仅 PDF 生成需要

# 设置环境变量
export LLM_API_KEY=sk-xxx
export FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx

# 抓取昨日数据（日报模式）
python monitor.py run --period day

# 仅生成报告（从飞书多维表格读取，不抓取新数据）
python monitor.py report --format html --period week

# 仅生成 PDF（需先生成 HTML，使用 PC 端版本）
python generate_pdf.py

# 发送日报飞书通知（本地测试）
python daily_check.py

# 测试写入飞书多维表格（取数据库最新 5 条）
FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx \
FEISHU_BITABLE_APP_TOKEN=BmXXX FEISHU_BITABLE_TABLE_ID=tblXXX \
python feishu_bitable.py

# 发送周报飞书通知（本地测试）
REPORT_MOBILE_URL=https://... REPORT_PC_URL=https://... python feishu_notify.py

# 关键词搜索数据库
python monitor.py query --keyword "loot box"

# 查看数据库统计
python monitor.py stats

# 重新翻译历史条目（更新 Prompt 后使用，每次最多 60 条）
python monitor.py retranslate --limit 60
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | 硅基流动 API Key | 必填 |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.siliconflow.cn/v1` |
| `LLM_MODEL` | 使用的模型 | `Qwen/Qwen3-8B` |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook 地址 | 必填（通知功能） |
| `FEISHU_APP_ID` | 飞书自建应用 App ID | 可选（多维表格读写） |
| `FEISHU_APP_SECRET` | 飞书自建应用 App Secret | 可选（多维表格读写） |
| `FEISHU_BITABLE_APP_TOKEN` | 多维表格 app_token | 可选（多维表格读写） |
| `FEISHU_BITABLE_TABLE_ID` | 多维表格 table_id | 可选（多维表格读写） |
| `REPORT_MOBILE_URL` | 周报移动端 HTML 链接（飞书卡片按钮） | 可选 |
| `REPORT_PC_URL` | 周报 PC 端 HTML 链接（飞书卡片按钮） | 可选 |

---

## 报告访问

| 文件 | 说明 |
|------|------|
| `reports/latest-mobile.html` | 最新移动端报告，GitHub Pages 直接访问 |
| `reports/latest-pc.html` | 最新 PC 端报告，适合宽屏阅读和 PDF 打印 |
| `reports/archive/YYYY-WXX/` | 历史周报 HTML 存档（按 ISO 周号归档） |

> PDF 仅在周报发布时按需生成，不长期入库（避免 git 历史膨胀）。

---

## 技术说明

- **LLM**：硅基流动免费层 `Qwen/Qwen3-8B`，每批 3 条并行处理，批间 4 秒冷却（遵守免费层限速）；Qwen3 系列默认关闭思维链（`enable_thinking: false`）以提速
- **去重机制**：四重保障 —— URL 精确匹配（全局）→ 事件指纹预筛（实体 + 议题）→ Bigram 相似度（同区域 > 0.45）→ LLM 批量核验；官方来源（tier=4）与任何同指纹条目 bigram > 0.20 即自动合并
- **Bitable 作为 SSOT**：所有条目经 `daily_check.py` 质量过滤后写入飞书多维表格，由团队人工初筛；周报从 Bitable 读取已审条目，确保报告内容质量
- **字体**：Inter Variable + JetBrains Mono 自托管于 `assets/fonts/`，通过 GitHub Pages CDN 分发，无外链依赖
- **数据库**：SQLite，存储在 `data/monitor.db`，每次 CI 运行后自动提交回仓库
- **PDF 生成**：Playwright Chromium 渲染 PC 端 HTML（A3 横向），GitHub Actions 已配置浏览器缓存
- **Git 优化**：所有 workflow 使用 `fetch-depth: 1` 浅克隆；PDF 不长期入库；CI push 前执行 `git pull --rebase` 避免并发冲突

---

*Lilith Legal · 仅供内部参考*
