# 🌐 Lilith Legal · 全球游戏立法动态监控

> 面向中资手游出海合规团队的自动化法规情报工具，每日追踪全球主要市场的游戏监管动态。

---

## 功能概览

- **自动抓取**：从 30+ 个官方监管机构、法律媒体、行业资讯 RSS 源实时获取法规动态
- **AI 翻译与提炼**：基于硅基流动 Qwen2.5-7B 将英文原文转化为规范中文标题和合规摘要，专有名词（Loot Box、GDPR、FTC 等）自动保留英文
- **智能分类**：按地区（东南亚 / 南亚 / 欧洲 / 北美 / 日韩台 等）和合规类别（数据隐私 / 未成年人保护 / 玩法合规 / 广告营销 等）自动归类
- **语义去重**：跨来源的同主题报道自动合并，避免重复阅读
- **HTML 报告**：生成可交互的 HTML 报告，支持按地区、分类、状态筛选和关键词搜索
- **PDF 报告**：每周自动生成带 Lilith Legal 品牌的 PDF 版本，方便分发存档
- **飞书通知**：每日有新动态时自动推送飞书卡片，含中文标题、摘要和原文链接
- **周报存档**：每周报告自动归档至 `reports/archive/YYYY-WW/`，支持后续趋势分析

---

## 自动化调度

| 任务 | 触发时间 | 说明 |
|------|----------|------|
| 日报 | 周一至周五 09:33 (SGT) | 抓取昨日新增，有更新则推送飞书 |
| 周报 | 每周一 09:47 (SGT) | 生成过去 7 天完整报告，发送飞书并存档 |

---

## 覆盖地区与来源

| 地区 | 代表来源 |
|------|----------|
| 北美 | FTC、纽约州 AG、加拿大竞争局 |
| 欧洲 | GDPR 执法动态、ASA（英国）、Ofcom、PEGI |
| 日韩台 | GRAC（韩国）、日本 CERO、台湾数位部 |
| 东南亚 | 越南信息通信部、印尼 Kominfo、泰国 NBTC |
| 南亚 | 印度 MeitY、IT 规则动态 |
| 全球 | GamesIndustry.biz、GamesBeat、IAPP |

---

## 本地使用

```bash
# 安装依赖
pip install -r requirements.txt

# 抓取并翻译最新数据，生成报告
python monitor.py run

# 只生成报告（不抓取）
python monitor.py report --format html

# 关键词搜索
python monitor.py query --keyword "loot box"

# 查看数据库统计
python monitor.py stats

# 刷新历史脏翻译（更新 prompt 后使用）
python monitor.py retranslate
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `LLM_API_KEY` | 硅基流动 API Key | 必填 |
| `LLM_BASE_URL` | LLM API 地址 | `https://api.siliconflow.cn/v1` |
| `LLM_MODEL` | 使用的模型 | `Qwen/Qwen2.5-7B-Instruct` |
| `FEISHU_WEBHOOK_URL` | 飞书 Webhook 地址 | 可选 |

---

## 报告示例

最新 HTML 报告：[`reports/latest.html`](reports/latest.html)

历史周报存档：[`reports/archive/`](reports/archive/)

---

*Lilith Legal · 仅供内部参考*
