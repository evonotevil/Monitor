#!/usr/bin/env python3
"""
全球游戏行业立法动态监控工具 - 主入口
面向中资手游出海合规 (以原神发行方式为参考)

用法:
    python monitor.py run                    # 执行一次完整抓取
    python monitor.py run --period week      # 周报 (近7天)
    python monitor.py run --period month     # 月报 (近30天)
    python monitor.py report                 # 从数据库生成报告
    python monitor.py report --period week   # 周报
    python monitor.py report --period month  # 月报
    python monitor.py report --format html   # 生成 HTML 报告
    python monitor.py query --keyword "loot box"  # 关键词搜索
    python monitor.py stats                  # 查看数据库统计
    python monitor.py schedule --interval 24 # 每24小时自动执行
"""

import argparse
import logging
import sys
import time
from datetime import datetime

from models import Database
from fetcher import fetch_and_process
from translator import translate_item_fields
from reporter import print_table, save_markdown, save_html, generate_markdown
from config import PERIOD_DAYS

# ─── 日志配置 ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/monitor.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _period_to_days(period: str) -> int:
    """将周期名称转为天数"""
    return PERIOD_DAYS.get(period, PERIOD_DAYS["all"])


def _period_label(period: str) -> str:
    labels = {"week": "周报（近7天）", "month": "月报（近30天）", "all": "全量报告"}
    return labels.get(period, "全量报告")


# ─── 命令: run ───────────────────────────────────────────────────────

def cmd_run(args):
    """执行一次完整的抓取-处理-存储流程"""
    days = _period_to_days(args.period)
    label = _period_label(args.period)
    logger.info(f"开始执行抓取 [{label}]...")
    db = Database()

    try:
        items = fetch_and_process(max_days=days)

        if items:
            no_translate = getattr(args, 'no_translate', False)
            if no_translate:
                logger.info("已跳过翻译 (--no-translate)")
            else:
                logger.info(f"正在翻译摘要 ({len(items)} 条)...")
                for item in items:
                    item_dict = item.to_dict()
                    translated = translate_item_fields(item_dict)
                    # 标题保留原文，只更新摘要中文翻译
                    item.summary_zh = translated.get("summary_zh", "")

            new_count = db.bulk_upsert(items)
            logger.info(f"新增 {new_count} 条记录 (共处理 {len(items)} 条)")
            db.log_fetch("full_run", new_count, "ok")
        else:
            logger.info("本次抓取未获取到新数据")
            db.log_fetch("full_run", 0, "ok", "no new items")

        all_items = db.query_items(days=days)
        if all_items:
            print_table(all_items)

            if args.output:
                if args.output.endswith(".html"):
                    path = save_html(all_items, args.output, period_label=label)
                else:
                    path = save_markdown(all_items, args.output)
                logger.info(f"报告已保存到: {path}")
            else:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                prefix = {"week": "weekly", "month": "monthly", "all": "report"}.get(args.period, "report")
                md_path = save_markdown(all_items, f"{prefix}_{ts}.md")
                html_path = save_html(all_items, f"{prefix}_{ts}.html", period_label=label)
                logger.info(f"Markdown 报告: {md_path}")
                logger.info(f"HTML 报告: {html_path}")

    except Exception as e:
        logger.error(f"抓取执行失败: {e}", exc_info=True)
        db.log_fetch("full_run", 0, "error", str(e))
    finally:
        db.close()


# ─── 命令: report ────────────────────────────────────────────────────

def cmd_report(args):
    """从数据库生成报告"""
    days = _period_to_days(args.period)
    label = _period_label(args.period)
    db = Database()
    try:
        items = db.query_items(
            region=args.region,
            category_l1=args.category,
            status=args.status,
            keyword=args.keyword,
            days=days,
        )

        if not items:
            print(f"数据库中暂无 [{label}] 匹配数据。请先运行 `python monitor.py run` 抓取数据。")
            return

        fmt = args.format.lower()
        if fmt == "table":
            print_table(items)
        elif fmt in ("markdown", "md"):
            path = save_markdown(items, args.output) if args.output else save_markdown(items)
            print(f"Markdown 报告已保存到: {path}")
        elif fmt == "html":
            path = (save_html(items, args.output, period_label=label) if args.output
                    else save_html(items, period_label=label))
            print(f"HTML 报告已保存到: {path}")
        else:
            print_table(items)

    finally:
        db.close()


# ─── 命令: query ─────────────────────────────────────────────────────

def cmd_query(args):
    """关键词查询"""
    db = Database()
    try:
        days = _period_to_days(getattr(args, 'period', 'all'))
        items = db.query_items(
            region=args.region,
            keyword=args.keyword,
            days=days,
        )
        if items:
            print_table(items)
        else:
            print("未找到匹配的记录。")
    finally:
        db.close()


# ─── 命令: stats ─────────────────────────────────────────────────────

def cmd_stats(args):
    """查看数据库统计信息"""
    db = Database()
    try:
        stats = db.get_stats()
        print()
        print(f"{'='*50}")
        print(f"  数据库统计")
        print(f"{'='*50}")
        print(f"  总记录数: {stats['total']}")
        print(f"  最新日期: {stats['latest_date'] or 'N/A'}")
        print()

        if stats["by_region"]:
            print(f"  按地区分布:")
            for region, cnt in stats["by_region"].items():
                bar = "█" * min(cnt, 30)
                print(f"    {region:<12} {cnt:>4}  {bar}")
            print()

        if stats["by_category"]:
            print(f"  按分类分布:")
            for cat, cnt in stats["by_category"].items():
                bar = "█" * min(cnt, 30)
                print(f"    {cat:<12} {cnt:>4}  {bar}")
            print()

    finally:
        db.close()


# ─── 命令: schedule ──────────────────────────────────────────────────

def cmd_schedule(args):
    """定时调度执行"""
    interval_hours = args.interval
    logger.info(f"启动定时监控, 间隔 {interval_hours} 小时")
    logger.info("按 Ctrl+C 停止")

    while True:
        try:
            logger.info(f"{'='*40} 定时任务开始 {'='*40}")
            cmd_run(args)
            logger.info(f"下次执行时间: {interval_hours} 小时后")
            time.sleep(interval_hours * 3600)
        except KeyboardInterrupt:
            logger.info("定时任务已停止")
            break
        except Exception as e:
            logger.error(f"定时任务异常: {e}", exc_info=True)
            logger.info(f"将在 {interval_hours} 小时后重试")
            time.sleep(interval_hours * 3600)


# ─── CLI 参数解析 ─────────────────────────────────────────────────────

def _add_period_arg(p):
    p.add_argument(
        "--period", "-p",
        choices=["week", "month", "all"],
        default="all",
        help="报告周期: week=周报(近7天)  month=月报(近30天)  all=全量(默认)",
    )


def main():
    parser = argparse.ArgumentParser(
        description="全球游戏行业立法动态监控工具 (中资手游出海合规视角)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    # run
    p_run = subparsers.add_parser("run", help="执行一次完整抓取并生成报告")
    _add_period_arg(p_run)
    p_run.add_argument("--output", "-o", help="输出文件名 (支持 .md / .html)")
    p_run.add_argument("--no-translate", action="store_true", help="跳过翻译(加快速度)")
    p_run.set_defaults(func=cmd_run)

    # report
    p_report = subparsers.add_parser("report", help="从数据库生成报告")
    p_report.add_argument("--format", "-f", default="html",
                          choices=["table", "markdown", "md", "html"],
                          help="输出格式 (默认 html)")
    _add_period_arg(p_report)
    p_report.add_argument("--region", "-r", help="按地区筛选")
    p_report.add_argument("--category", "-c", help="按一级分类筛选")
    p_report.add_argument("--status", "-s", help="按状态筛选")
    p_report.add_argument("--keyword", "-k", help="关键词过滤")
    p_report.add_argument("--output", "-o", help="输出文件名")
    p_report.set_defaults(func=cmd_report)

    # query
    p_query = subparsers.add_parser("query", help="关键词查询")
    p_query.add_argument("--keyword", "-k", required=True, help="搜索关键词")
    p_query.add_argument("--region", "-r", help="按地区筛选")
    _add_period_arg(p_query)
    p_query.set_defaults(func=cmd_query)

    # stats
    p_stats = subparsers.add_parser("stats", help="查看数据库统计")
    p_stats.set_defaults(func=cmd_stats)

    # schedule
    p_schedule = subparsers.add_parser("schedule", help="定时自动执行")
    p_schedule.add_argument("--interval", type=float, default=24,
                            help="执行间隔(小时), 默认24")
    _add_period_arg(p_schedule)
    p_schedule.add_argument("--output", "-o", help="输出文件名")
    p_schedule.set_defaults(func=cmd_schedule)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
