# 全球游戏合规动态监控

一个用于整理公开信息的自动化监控工具，聚合游戏行业相关的监管、执法、诉讼和平台政策动态。

## 主要能力

- 从公开订阅源、新闻索引和官方页面采集信息
- 处理多语种内容并生成统一的结构化结果
- 过滤常见噪音，合并重复或高度相似的事件
- 对候选内容进行分类、摘要和优先级辅助判断
- 支持定时运行、数据查询和报告生成
- 可按需连接外部协作与通知服务

## 快速开始

建议使用 Python 3.11。

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python monitor.py --help
```

执行一次采集：

```bash
python monitor.py run --period day
```

查看已有数据或生成报告：

```bash
python monitor.py stats
python monitor.py report --period week
```

外部服务凭据通过环境变量或仓库密钥提供。实际运行前，请根据部署环境完成必要配置。
日报可通过 `DAILY_DASHBOARD_URL` 配置统计概览下方的合规看板入口；未设置时不显示按钮。

## 测试

```bash
python -m pytest tests/ -q
```

## 安全说明

- 不要将访问密钥、令牌、聊天或数据表标识提交到仓库
- 运行数据、日志和生成报告可能包含非公开信息，应按实际权限要求保存
- 对外部服务启用写入或推送前，应先确认目标、权限和数据范围

## 说明

自动分类和摘要仅用于信息初筛，不能替代专业判断。使用者应结合原始来源核实内容及其适用范围。
