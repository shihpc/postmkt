#!/usr/bin/env python3
# tests/test_revenue_frontend.py —— 代跑 tests/test_revenue_frontend.mjs（月營收 tab 前端純函式＋靜態守門，
# 2026-11-12 階段二，規格 docs/revenue-beatmiss.md §5）。需要 node；免網路、免 token。
from __future__ import annotations

import os
import shutil
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def test_revenue_frontend_pure_functions():
    node = shutil.which("node")
    if not node:
        pytest.fail("找不到 node：本測試需要 node 執行 index.html 抽出的前端函式")
    out = subprocess.run([node, os.path.join(ROOT, "tests", "test_revenue_frontend.mjs")],
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stdout + out.stderr
