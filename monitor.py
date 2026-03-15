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
from translator import translate_items_batch
from reporter import print_table, save_markdown, save_html, generate_markdown
from utils import _get_region_group, _bigram_sim
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
    if period == "day":
        return 1
    return PERIOD_DAYS.get(period, PERIOD_DAYS["all"])


# ─── 语义去重（同地区/同日期窗口内高度相似的文章只保留一条）────────────

def _make_timeline_note(items_group: list) -> str:
    """
    将多个同主题条目（不同日期/状态）合并为时间轴注释。
    返回格式：进展：YYYY-MM-DD [状态1] → YYYY-MM-DD [状态2] ...
    """
    stages = sorted(
        {(item.date, item.status) for item in items_group},
        key=lambda x: x[0],
    )
    if len(stages) <= 1:
        return ""
    parts = " → ".join(f"{d} [{s}]" for d, s in stages)
    return f"进展：{parts}"


def _deduplicate_items(items):
    """
    两阶段去重 + 事件级时间轴合并：

    【阶段 1 — 当日去重（2 天窗口）】
      同 region + 日期差 ≤2 天 + bigram 相似度 >0.8 → 确定重复，保留高分项。

    【阶段 2 — 事件级聚类（14 天窗口）】
      同 region + 同 category_l1 + 日期差 2–14 天 + 相似度 0.5–0.8
      → 候选为"同一监管事件的不同进展阶段"
      → 用 LLM verify_duplicate_pairs 确认（无 LLM 则用相似度 >0.65 启发式判断）
      → 确认后：保留状态权重最高项，并在其 summary_zh 末尾追加时间轴进展注释

    禁止跨 region 合并（如美国 vs 英国同主题法案仍独立显示）。
    """
    from models import LegislationItem
    from datetime import date as _date
    dropped: set[int] = set()

    # ── 阶段 1：2 天窗口，高置信去重 ────────────────────────────────────
    for i, item_i in enumerate(items):
        if i in dropped:
            continue
        duplicates = []
        for j, item_j in enumerate(items):
            if j <= i or j in dropped:
                continue
            if item_i.region != item_j.region:
                continue
            try:
                d_i = _date.fromisoformat(item_i.date)
                d_j = _date.fromisoformat(item_j.date)
                diff = abs((d_i - d_j).days)
                if diff > 2:
                    continue
            except ValueError:
                continue
            sim = _bigram_sim(item_i.title, item_j.title)
            if sim > 0.8:
                duplicates.append((j, sim))
        if duplicates:
            group = [(i, 0.0)] + duplicates
            group.sort(key=lambda x: (-items[x[0]].impact_score, x[0]))
            winner_idx = group[0][0]
            for idx, _ in group[1:]:
                dropped.add(idx)

    # ── 阶段 2：30 天窗口，事件级聚类（硬性合并同一法案不同阶段）────────
    # 同一法案在不同阶段（如印尼年龄禁令草案→已生效）严禁拆分展示，必须合并。
    # 窗口扩展至 30 天；移除相似度上限（sim > 0.8 的高相似跨阶段对同样捕获）。
    # 状态优先级（高 → 低）
    _STATUS_RANK = {
        "已生效": 9, "即将生效": 8, "执法动态": 7, "修订变更": 6,
        "草案/征求意见": 5, "立法进行中": 4, "已提案": 3, "立法动态": 2, "已废止": 1,
    }

    # 收集候选跨阶段对：(i, j)
    candidates = []
    for i, item_i in enumerate(items):
        if i in dropped:
            continue
        for j, item_j in enumerate(items):
            if j <= i or j in dropped:
                continue
            # 同 region + 同大类
            if item_i.region != item_j.region:
                continue
            if item_i.category_l1 != item_j.category_l1:
                continue
            try:
                d_i = _date.fromisoformat(item_i.date)
                d_j = _date.fromisoformat(item_j.date)
                diff = abs((d_i - d_j).days)
                if diff <= 2 or diff > 30:   # 2 天内已处理，>30 天不合并
                    continue
            except ValueError:
                continue
            sim = _bigram_sim(item_i.title, item_j.title)
            # 移除上限：sim ≥ 0.5 均为候选（高相似跨阶段对在 LLM 验证后合并）
            if sim >= 0.5:
                candidates.append((i, j, sim))

    if candidates:
        # 尝试用 LLM 批量验证
        pairs_to_verify = []
        for i, j, _ in candidates:
            t_i = (items[i].title_zh or items[i].title or "")
            t_j = (items[j].title_zh or items[j].title or "")
            pairs_to_verify.append((t_i, t_j))

        llm_results = None
        try:
            from translator import verify_duplicate_pairs
            import time as _time
            _time.sleep(2)
            llm_results = verify_duplicate_pairs(pairs_to_verify)
        except Exception as e:
            logger.warning(f"[事件聚类] LLM 验证失败，使用启发式判断: {e}")

        for idx_pair, (i, j, sim) in enumerate(candidates):
            if i in dropped or j in dropped:
                continue
            is_same_event = (
                llm_results[idx_pair]
                if llm_results and idx_pair < len(llm_results)
                else sim >= 0.65  # 无 LLM 时：高相似度 + 同地区同类 → 视为同一事件
            )
            if not is_same_event:
                continue

            item_i, item_j = items[i], items[j]
            # 保留状态优先级更高的项（草案→生效 保留"生效"条目）
            rank_i = _STATUS_RANK.get(item_i.status, 0)
            rank_j = _STATUS_RANK.get(item_j.status, 0)
            if rank_i >= rank_j:
                winner, loser_idx = i, j
            else:
                winner, loser_idx = j, i

            dropped.add(loser_idx)
            timeline = _make_timeline_note([item_i, item_j])
            if timeline:
                winner_item = items[winner]
                if winner_item.summary_zh:
                    winner_item.summary_zh = winner_item.summary_zh.rstrip("。") + f"。{timeline}"
                else:
                    winner_item.summary_zh = timeline
                logger.info(
                    f"[事件聚类] 合并跨阶段条目 → {timeline[:60]}"
                )

    result = [item for i, item in enumerate(items) if i not in dropped]
    merged = len(items) - len(result)
    if merged:
        logger.info(
            f"[去重] 两阶段去重：{len(items)} 条 → {len(result)} 条（合并 {merged} 条）"
        )
    return result


def _filter_valid_dates(items):
    """
    过滤掉日期不在合理范围内的条目（避免 RSS 日期回收等导致的噪音入库）。
    保留当年及前一年的条目。
    """
    current_year = datetime.now().year
    valid_years = {str(current_year), str(current_year - 1)}
    valid = [item for item in items if (item.date or "")[:4] in valid_years]
    removed = len(items) - len(valid)
    if removed:
        logger.info(
            f"[日期过滤] 移除 {removed} 条日期不在 "
            f"{current_year - 1}-{current_year} 的条目"
        )
    return valid


def _period_label(period: str) -> str:
    if period == "week":
        return datetime.utcnow().strftime("%G-W%V")
    labels = {"day": "日报（昨日）", "month": "月报（近30天）", "all": "全量报告"}
    return labels.get(period, "全量报告")


# ─── 命令: run ───────────────────────────────────────────────────────

def cmd_run(args):
    """执行一次完整的抓取-处理-存储流程"""
    days = _period_to_days(args.period)
    label = _period_label(args.period)
    logger.info(f"开始执行抓取 [{label}]...")
    db = Database()

    daily_mode = (args.period == "day")
    try:
        items = fetch_and_process(max_days=days, daily_mode=daily_mode)

        if items:
            # 严格日期过滤：只保留 2025/2026 年的条目
            items = _filter_valid_dates(items)
            # 语义去重：同 region 同日期窗口内高度相似的文章合并为一条
            items = _deduplicate_items(items)

            no_translate = getattr(args, 'no_translate', False)
            if no_translate:
                logger.info("已跳过翻译 (--no-translate)")
            else:
                from classifier import score_impact
                logger.info(f"正在批量翻译并分类 ({len(items)} 条，每批 3 篇)...")
                kept_items = []
                llm_filtered = 0

                # ── 批量翻译：3 条/LLM 请求，速度 3× ─────────────────
                items_dicts = [item.to_dict() for item in items]
                translated_list = translate_items_batch(items_dicts, batch_size=3)

                for item, translated in zip(items, translated_list):
                    # ── LLM 相关性过滤 ─────────────────────────────────
                    if translated.get("_llm_is_relevant") is False:
                        llm_filtered += 1
                        continue

                    item.summary_zh = translated.get("summary_zh", "")
                    item.title_zh   = translated.get("title_zh", "")

                    # ── 应用 LLM 分类结果（覆盖正则，空值保留正则原值）──
                    llm_region   = translated.get("_llm_region", "")
                    llm_category = translated.get("_llm_category_l1", "")
                    llm_status   = translated.get("_llm_status", "")

                    if llm_region:
                        item.region = llm_region
                    if llm_category:
                        item.category_l1 = llm_category
                    if llm_status and llm_status != item.status:
                        logger.info(
                            f"[LLM分类] 状态更新 '{item.status}' → '{llm_status}'"
                            f" | {item.title[:50]}"
                        )
                        item.status = llm_status
                        item.impact_score = score_impact(
                            item.status,
                            item.source_name,
                            region=item.region,
                            text=f"{item.title} {item.summary_zh}",
                        )

                    kept_items.append(item)

                if llm_filtered:
                    logger.info(
                        f"[LLM过滤] 共过滤 {llm_filtered} 条不相关文章，"
                        f"保留 {len(kept_items)} 条"
                    )
                items = kept_items

            new_count = db.bulk_upsert(items)
            logger.info(f"新增 {new_count} 条记录 (共处理 {len(items)} 条)")
            db.log_fetch("full_run", new_count, "ok")

        else:
            logger.info("本次抓取未获取到新数据")
            db.log_fetch("full_run", 0, "ok", "no new items")

        all_items = db.query_items(days=days)
        if all_items:
            print_table(all_items)

            if args.output and not args.output.endswith(".html"):
                path = save_markdown(all_items, args.output)
                logger.info(f"报告已保存到: {path}")
            else:
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                prefix = {"week": "weekly", "month": "monthly", "all": "report"}.get(args.period, "report")
                md_path = save_markdown(all_items, f"{prefix}_{ts}.md")
                mobile_path, pc_path = save_html(all_items, period_label=label)
                logger.info(f"Markdown 报告: {md_path}")
                logger.info(f"移动端 HTML: {mobile_path}")
                logger.info(f"PC 端 HTML:  {pc_path}")

    except Exception as e:
        logger.error(f"抓取执行失败: {e}", exc_info=True)
        db.log_fetch("full_run", 0, "error", str(e))
    finally:
        db.close()


# ─── 命令: report ────────────────────────────────────────────────────

def cmd_report(args):
    """
    生成 HTML / Markdown / 终端报告。

    数据来源优先级：
      1. 飞书多维表格（SSOT）——仅包含人工筛选过的有效记录
         （「处理状态」≠ 待初筛 且 ≠ 噪音/不推送）
      2. 本地 SQLite 数据库（回退）——Bitable 凭证未配置或返回空时启用
    """
    days  = _period_to_days(args.period)
    label = _period_label(args.period)
    fmt   = args.format.lower()

    # ── Step 1: 优先从飞书多维表格（SSOT）拉取经人工筛选的记录 ──────────
    from feishu_bitable import fetch_valid_records_from_bitable
    print(f"📋 尝试从飞书多维表格读取数据（{label}）…")
    items = fetch_valid_records_from_bitable(days=days)

    # ── Step 2: Bitable 无数据时回退到 SQLite ────────────────────────────
    if not items:
        print("⚠️  Bitable 无有效数据，回退到本地 SQLite 数据库…")
        db = Database()
        try:
            items = db.query_items(
                region=getattr(args, "region", None),
                category_l1=getattr(args, "category", None),
                status=getattr(args, "status", None),
                keyword=getattr(args, "keyword", None),
                days=days,
            )
        finally:
            db.close()

    if not items:
        print(f"暂无 [{label}] 有效数据（飞书多维表格和数据库均无匹配记录）。")
        return

    print(f"📊 共获取 {len(items)} 条有效记录，开始生成 [{label}] 报告…")

    if fmt == "table":
        print_table(items)
    elif fmt in ("markdown", "md"):
        path = save_markdown(items, args.output) if args.output else save_markdown(items)
        print(f"Markdown 报告已保存到: {path}")
    elif fmt == "html":
        mobile_path, pc_path = save_html(items, period_label=label)
        print(f"移动端 HTML 已保存到: {mobile_path}")
        print(f"PC 端 HTML 已保存到:  {pc_path}")
    else:
        print_table(items)


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


# ─── 命令: retranslate ───────────────────────────────────────────────

def cmd_retranslate(args):
    """
    清空含脏词/格式问题的历史翻译字段，然后立即重新翻译。
    用途：当 translator.py 中的 _TERM_CORRECTIONS 或 prompt 更新后，
    让旧数据库条目也能享受最新翻译质量。
    """
    from translator import _TERM_CORRECTIONS, translate_item_fields

    db = Database()
    try:
        # ── 阶段 1：清空含脏词的翻译字段 ──────────────────────────────
        dirty_terms = list(_TERM_CORRECTIONS.keys())
        # 同时清理常见格式问题：【xxx】栏目前缀、问句标题（以"？"结尾）
        extra_patterns = ["【"]
        cleared = db.clear_stale_translations(dirty_terms + extra_patterns)
        logger.info(f"[重译] 已清空 {cleared} 条含脏词翻译的条目")

        # ── 阶段 2：查询所有 title_zh 为空的条目并重译 ─────────────────
        # 注意：即使 cleared==0（无脏词），--no-translate 抓取的新条目也需要在这里翻译，
        # 因此不提前返回，让下方的 items_dicts 为空判断处理"真正无事可做"的情形。
        limit = getattr(args, "limit", 100)
        items_dicts = db.query_items_untranslated(limit=limit)
        if not items_dicts:
            logger.info("[重译] 没有待翻译条目，完成。")
            return

        logger.info(f"[重译] 开始重译 {len(items_dicts)} 条条目（限额 {limit}）…")
        updated = 0
        deleted = 0
        for item_dict in items_dicts:
            translated = translate_item_fields(item_dict)
            # LLM 判定不相关：直接从 DB 删除，避免报告出现大量未翻译低价值条目
            if translated.get("_llm_is_relevant") is False:
                db.delete_item(item_dict["id"])
                deleted += 1
                logger.info(f"  ✗ [删除] [{item_dict.get('region','')}] {item_dict.get('title','')[:40]}")
                continue
            if translated.get("title_zh"):
                db.update_translation(
                    item_dict["id"],
                    translated["title_zh"],
                    translated.get("summary_zh", ""),
                )
                updated += 1
                logger.info(f"  ✓ [{item_dict.get('region','')}] {translated['title_zh'][:40]}")
        if deleted:
            logger.info(f"[重译] 删除 {deleted} 条 LLM 判定不相关条目")
        logger.info(f"[重译] 完成，共更新 {updated} 条。")
    finally:
        db.close()


# ─── 命令: noise-sync ────────────────────────────────────────────────

def cmd_noise_sync(args):
    """
    从 Bitable 读取「🗑️ 噪音/不推送」记录，统计各信源出现次数，
    将超过阈值的信源写入 data/noise_sources.json。
    classifier.py 启动时自动加载该文件，对高噪音信源降低 impact_score。
    """
    import json
    from pathlib import Path
    from feishu_bitable import fetch_noise_source_stats
    from classifier import _reload_noise_sources

    logger.info("[噪音同步] 从 Bitable 读取噪音记录…")
    stats = fetch_noise_source_stats()
    if not stats:
        logger.warning("[噪音同步] 未获取到噪音统计（Bitable 未配置或无噪音记录）")
        return

    threshold = args.threshold
    blocklist = [k for k, v in stats.items() if v >= threshold]

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d"),
        "threshold":  threshold,
        "stats":      stats,
        "blocklist":  blocklist,
    }

    path = Path("data/noise_sources.json")
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    logger.info(
        f"[噪音同步] 已更新：{len(stats)} 个信源统计，"
        f"{len(blocklist)} 个高噪音信源（阈值 ≥{threshold} 条）"
    )
    print("\n信源噪音排行（前 15）：")
    for src, cnt in list(stats.items())[:15]:
        flag = "🚫" if src in set(blocklist) else "  "
        print(f"  {flag} {cnt:3d}x  {src}")

    # 让当前进程内的 classifier 立即生效
    _reload_noise_sources()


# ─── 命令: archive ────────────────────────────────────────────────────

def cmd_archive(args):
    """
    将超过 keep_days 天以前的 DB 记录归档到 legislation_archive 表并从主表删除，
    回收 SQLite 磁盘空间。建议每月执行一次（GitHub Actions 月度定时任务）。
    """
    db = Database()
    try:
        keep_days = args.keep_days
        logger.info(f"[归档] 将 {keep_days} 天以前的记录移入 legislation_archive …")
        count = db.archive_old_records(keep_days=keep_days)
        logger.info(
            f"[归档] 完成：归档 {count} 条，主表保留近 {keep_days} 天数据"
        )
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
        choices=["day", "week", "month", "all"],
        default="all",
        help="报告周期: day=日报(昨日,when:1d)  week=周报(近7天)  month=月报(近30天)  all=全量(默认)",
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

    # retranslate
    p_retrans = subparsers.add_parser(
        "retranslate",
        help="清空含脏词/格式问题的历史翻译并重新生成（prompt 更新后用）",
    )
    p_retrans.add_argument(
        "--force", action="store_true",
        help="即使没有检测到脏词也强制重译全部 title_zh 为空的条目",
    )
    p_retrans.add_argument(
        "--limit", type=int, default=100,
        help="单次最多重译条数（默认 100，避免超 Groq 配额）",
    )
    p_retrans.set_defaults(func=cmd_retranslate)

    # noise-sync
    p_noise = subparsers.add_parser(
        "noise-sync",
        help="从 Bitable 同步噪音来源统计，更新 data/noise_sources.json",
    )
    p_noise.add_argument(
        "--threshold", type=int, default=5,
        help="噪音次数阈值，达到此值的信源进入降分名单（默认 5）",
    )
    p_noise.set_defaults(func=cmd_noise_sync)

    # archive
    p_archive = subparsers.add_parser(
        "archive",
        help="将旧记录归档到 legislation_archive 表并压缩数据库",
    )
    p_archive.add_argument(
        "--keep-days", type=int, default=180,
        help="保留最近 N 天的主表数据（默认 180 天）",
    )
    p_archive.set_defaults(func=cmd_archive)

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
