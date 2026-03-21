"""
RSS 自动发现脚本
探测 OFFICIAL_SITE_QUERIES 中涉及的官方域名是否存在未收录的 RSS/Atom feed。
用法: python discover_rss.py
"""

import time
import xml.etree.ElementTree as ET
import concurrent.futures
from typing import Optional
import warnings
warnings.filterwarnings("ignore")
import requests

# ── 探测路径（从最常见到最少见）────────────────────────────────────────
PROBE_PATHS = [
    "/feed",
    "/feed.xml",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/feeds/all.atom.xml",
    "/feeds/posts/default",
    "/news/feed",
    "/news/rss",
    "/news.rss",
    "/news/rss.xml",
    "/press/feed",
    "/press-releases/feed",
    "/press/rss.xml",
    "/en/rss.xml",
    "/en/feed",
    "/en/news/rss",
    "/sitemap-news.xml",
    "/announcements/feed",
    "/notices/feed",
    "/publications/feed",
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
}

# ── 目标域名（来自 OFFICIAL_SITE_QUERIES + 额外补充）───────────────────
TARGETS = [
    # 北美
    {"domain": "ftc.gov",          "region": "北美",  "note": "已有 press-release RSS，看是否还有其他频道"},
    {"domain": "oag.ca.gov",       "region": "北美",  "note": "加州 AG"},
    {"domain": "commerce.gov",     "region": "北美",  "note": "美国商务部（新增候选）"},
    {"domain": "esrb.org",         "region": "北美",  "note": "ESRB 评级（新增候选）"},
    # 欧洲
    {"domain": "ico.org.uk",       "region": "欧洲",  "note": "UK 信息专员"},
    {"domain": "cnil.fr",          "region": "欧洲",  "note": "法国 CNIL"},
    {"domain": "bfdi.bund.de",     "region": "欧洲",  "note": "德国联邦数据保护局"},
    {"domain": "pegi.info",        "region": "欧洲",  "note": "欧洲 PEGI"},
    {"domain": "edpb.europa.eu",   "region": "欧洲",  "note": "已有 RSS，验证是否仍有效"},
    {"domain": "digital-strategy.ec.europa.eu", "region": "欧洲", "note": "EU 数字战略"},
    {"domain": "usk.de",           "region": "欧洲",  "note": "德国 USK 评级（新增候选）"},
    # 日本
    {"domain": "caa.go.jp",        "region": "日本",  "note": "消費者庁"},
    {"domain": "soumu.go.jp",      "region": "日本",  "note": "总务省（新增候选）"},
    {"domain": "meti.go.jp",       "region": "日本",  "note": "经产省（新增候选）"},
    {"domain": "cero.gr.jp",       "region": "日本",  "note": "CERO 游戏评级"},
    # 韩国
    {"domain": "grac.or.kr",       "region": "韩国",  "note": "韩国 GRAC"},
    {"domain": "moleg.go.kr",      "region": "韩国",  "note": "韩国法制处"},
    {"domain": "kftc.go.kr",       "region": "韩国",  "note": "韩国公正交易委员会"},
    {"domain": "kcc.go.kr",        "region": "韩国",  "note": "韩国通信委员会（新增候选）"},
    # 东南亚
    {"domain": "mic.gov.vn",       "region": "越南",  "note": "越南信息通信部"},
    {"domain": "kominfo.go.id",    "region": "印尼",  "note": "印尼 Kominfo"},
    {"domain": "pdpc.gov.sg",      "region": "新加坡","note": "新加坡个人数据保护委员会"},
    {"domain": "imda.gov.sg",      "region": "新加坡","note": "新加坡 IMDA"},
    {"domain": "mci.gov.sg",       "region": "新加坡","note": "新加坡通信信息部（新增候选）"},
    # 大洋洲
    {"domain": "accc.gov.au",      "region": "大洋洲","note": "澳大利亚 ACCC"},
    {"domain": "oaic.gov.au",      "region": "大洋洲","note": "澳大利亚信息专员"},
    {"domain": "acma.gov.au",      "region": "大洋洲","note": "澳大利亚 ACMA"},
    {"domain": "esafety.gov.au",   "region": "大洋洲","note": "澳大利亚 eSafety（之前 timeout）"},
    {"domain": "privacy.org.nz",   "region": "大洋洲","note": "新西兰隐私专员（新增候选）"},
    # 南亚
    {"domain": "meity.gov.in",     "region": "南亚",  "note": "印度电子信息技术部"},
    # 中东
    {"domain": "gcam.gov.sa",      "region": "中东",  "note": "沙特 GCAM"},
    {"domain": "tra.gov.ae",       "region": "中东",  "note": "阿联酋 TRA"},
    {"domain": "tdra.gov.ae",      "region": "中东",  "note": "阿联酋 TDRA（新增候选）"},
]

# 已知有效、已收录的 RSS（跳过重复收录提示）
ALREADY_IN_CONFIG = {
    "https://www.ftc.gov/feeds/press-release-consumer-protection.xml",
    "https://www.edpb.europa.eu/rss.xml",
    "https://developer.apple.com/news/rss/news.rss",
}


def is_valid_feed(content: bytes) -> bool:
    """检查响应内容是否是合法的 RSS/Atom feed。"""
    try:
        root = ET.fromstring(content)
        tag = root.tag.lower()
        # RSS 根节点: <rss>, Atom: <feed>
        if "rss" in tag or "feed" in tag:
            return True
        # 带命名空间的 Atom: {http://www.w3.org/2005/Atom}feed
        if "feed" in tag or "channel" in tag:
            return True
        # 检查是否有 <item> 或 <entry> 子节点
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        if root.findall(".//item") or root.findall(".//atom:entry", ns) or root.findall(".//entry"):
            return True
    except ET.ParseError:
        pass
    return False


def probe_url(url: str) -> Optional[str]:
    """探测单个 URL，有效返回 URL，否则返回 None。"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=6,
                            allow_redirects=True, stream=False)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if any(x in ct for x in ["xml", "rss", "atom"]) or is_valid_feed(resp.content):
                return url
    except Exception:
        pass
    return None


def probe_domain(target: dict) -> list:
    """对一个域名并发探测所有候选路径，返回找到的有效 feed URL 列表。"""
    domain = target["domain"]
    urls = [f"https://{domain}{path}" for path in PROBE_PATHS]
    found = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as ex:
        future_map = {ex.submit(probe_url, u): u for u in urls}
        # 给每个域名最多 20 秒总时间
        done, _ = concurrent.futures.wait(future_map, timeout=20)

    for f in done:
        result = f.result()
        if result:
            if result not in ALREADY_IN_CONFIG:
                found.append(result)
                print(f"    ✅ {result}", flush=True)
            else:
                print(f"    ☑️  {result}  ← 已收录", flush=True)
    return found


def main():
    print("=" * 64)
    print("RSS 自动发现扫描")
    print(f"目标: {len(TARGETS)} 个官方域名，{len(PROBE_PATHS)} 条探测路径")
    print("=" * 64)

    all_found = []

    for i, target in enumerate(TARGETS, 1):
        domain = target["domain"]
        region = target["region"]
        note   = target["note"]
        print(f"\n[{i:02d}/{len(TARGETS)}] {region} · {domain}")
        print(f"         {note}")

        found = probe_domain(target)
        if not found:
            print(f"    — 未发现有效 feed")
        else:
            for url in found:
                all_found.append({
                    "domain": domain,
                    "region": region,
                    "url": url,
                    "note": note,
                })

        time.sleep(0.5)

    # ── 汇总报告 ──────────────────────────────────────────────────────
    print("\n" + "=" * 64)
    print(f"扫描完成。共发现 {len(all_found)} 个未收录的有效 feed：")
    print("=" * 64)

    if not all_found:
        print("未发现新的可用 feed。")
    else:
        # 按地区分组打印
        by_region: dict = {}
        for item in all_found:
            by_region.setdefault(item["region"], []).append(item)

        for region, items in by_region.items():
            print(f"\n【{region}】")
            for item in items:
                print(f"  {item['domain']}")
                print(f"    URL:  {item['url']}")
                print(f"    说明: {item['note']}")

        print("\n── 可直接加入 config.py RSS_FEEDS 的配置片段 ──")
        for item in all_found:
            name = item["note"].split("（")[0].strip()
            print(f"""
    {{
        "name": "{name}",
        "url": "{item['url']}",
        "lang": "en",
        "type": "rss",
        "region": "{item['region']}",
        "tier": "official",
    }},""")


if __name__ == "__main__":
    main()
