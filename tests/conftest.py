"""
测试基础设施 — 将项目根目录加入 sys.path，使 import classifier / utils 等模块可用。
"""
import sys
from pathlib import Path

# 项目根目录（tests/ 的上级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
