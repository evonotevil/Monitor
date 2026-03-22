"""运行时配置：输出路径、数据库、超时、并发等"""

# ─── 输出配置 ─────────────────────────────────────────────────────────

OUTPUT_DIR = "reports"
DATABASE_PATH = "data/monitor.db"
MAX_ARTICLE_AGE_DAYS = 90
FETCH_TIMEOUT = 30
MAX_CONCURRENT_REQUESTS = 5

# 周报/月报对应天数
PERIOD_DAYS = {
    "week":  7,
    "month": 30,
    "all":   90,
}
