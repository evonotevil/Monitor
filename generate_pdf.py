#!/usr/bin/env python3
"""
PDF 生成器 - 将最新 HTML 报告转换为高质量 PDF
使用 Playwright (Chromium) 渲染，确保 CSS/JS 完整呈现

用法:
    python generate_pdf.py                          # 自动找最新 HTML
    python generate_pdf.py --input reports/xxx.html  # 指定输入
    python generate_pdf.py --input x.html --output x.pdf

安装依赖:
    pip install playwright
    playwright install chromium
"""

import argparse
import asyncio
import os
import shutil
import sys
from pathlib import Path

REPORTS_DIR = Path(__file__).parent / "reports"


def find_latest_html() -> Path:
    candidates = sorted(
        list(REPORTS_DIR.glob("report_*.html")) + list(REPORTS_DIR.glob("weekly_*.html")),
        key=os.path.getmtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(f"在 {REPORTS_DIR} 中找不到 HTML 报告")
    return candidates[0]


async def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("❌ Playwright 未安装。请运行:")
        print("   pip install playwright && playwright install chromium")
        sys.exit(1)

    print(f"📄 正在生成 PDF: {html_path.name} → {pdf_path.name}")

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        # 加载本地 HTML，等待 JS 渲染完成
        await page.goto(f"file://{html_path.absolute()}", wait_until="networkidle")
        await page.wait_for_timeout(800)

        await page.pdf(
            path=str(pdf_path),
            format="A3",
            landscape=True,
            print_background=True,
            margin={
                "top": "12mm",
                "bottom": "12mm",
                "left": "10mm",
                "right": "10mm",
            },
        )
        await browser.close()

    print(f"✅ PDF 已保存: {pdf_path}")


def main():
    parser = argparse.ArgumentParser(description="Convert latest HTML report to PDF")
    parser.add_argument("--input",  "-i", type=Path, default=None)
    parser.add_argument("--output", "-o", type=Path, default=None)
    args = parser.parse_args()

    html_path = args.input or find_latest_html()
    pdf_path  = args.output or html_path.with_suffix(".pdf")

    asyncio.run(html_to_pdf(html_path, pdf_path))

    # 同时写一份 latest.pdf，供固定链接使用
    latest_pdf = REPORTS_DIR / "latest.pdf"
    shutil.copy2(pdf_path, latest_pdf)
    print(f"📌 同步写入: {latest_pdf}")

    # 同时写一份 latest.html
    latest_html = REPORTS_DIR / "latest.html"
    shutil.copy2(html_path, latest_html)
    print(f"📌 同步写入: {latest_html}")


if __name__ == "__main__":
    main()
