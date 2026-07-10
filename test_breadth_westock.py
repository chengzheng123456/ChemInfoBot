# -*- coding: utf-8 -*-
"""涨跌分布主源（腾讯自选股 / westock-data CLI）单元测试。

覆盖：
  1. _parse_changedist_markdown 对真实 Markdown 的解析（字段映射正确）。
  2. 盘前全 0 / 解析失败 时诚实返回 None（不编造）。
  3. WESTOCK_CLI 未配置或路径不存在时，fetch_market_breadth_tencent_skill
     优雅返回 None（交由东方财富兜底），不抛异常。
"""
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config as _cfg
from a_stock_spider import AStockSpider

# 真实 changedist Markdown 概览片段（2026-07-09 收盘截面）
SAMPLE_MD = """### 市场涨跌分布（沪深A股）

| 上涨 | 下跌 | 平盘 | 涨停 | 跌停 | 停牌 | 上涨占比 |
| --- | --- | --- | --- | --- | --- | --- |
| 2486 | 2888 | 155 | 75 | 15 | 9 | 44% |

两市成交额：29137.22亿（较上日 +3501.99亿）

**涨跌幅区间分布**

| 区间 | 家数 | 方向 |
| --- | --- | --- |
| 涨停 | 75 | 涨 |
| >7% | 225 | 涨 |
"""


class TestParseChangedist(unittest.TestCase):
    def setUp(self):
        self.sp = AStockSpider()

    def test_parse_real_markdown(self):
        d = self.sp._parse_changedist_markdown(SAMPLE_MD)
        self.assertIsNotNone(d)
        self.assertEqual(d["up"], 2486)
        self.assertEqual(d["down"], 2888)
        self.assertEqual(d["flat"], 155)
        self.assertEqual(d["up_limit"], 75)
        self.assertEqual(d["down_limit"], 15)
        self.assertEqual(d["total"], 2486 + 2888 + 155)
        self.assertEqual(d["source"], "tencent-westock")
        self.assertEqual(d["top_gainers"], [])
        self.assertEqual(d["top_losers"], [])

    def test_parse_all_zero_returns_none(self):
        md = SAMPLE_MD.replace("2486", "0").replace("2888", "0").replace("155", "0")
        self.assertIsNone(self.sp._parse_changedist_markdown(md))

    def test_parse_garbage_returns_none(self):
        self.assertIsNone(self.sp._parse_changedist_markdown("no table here"))
        self.assertIsNone(self.sp._parse_changedist_markdown(""))


class TestTencentSkillGraceful(unittest.TestCase):
    def setUp(self):
        self.sp = AStockSpider()

    def test_unconfigured_cli_returns_none(self):
        saved = _cfg.WESTOCK_CLI
        _cfg.WESTOCK_CLI = ""
        try:
            self.assertIsNone(self.sp.fetch_market_breadth_tencent_skill())
        finally:
            _cfg.WESTOCK_CLI = saved

    def test_missing_cli_path_returns_none(self):
        saved = _cfg.WESTOCK_CLI
        _cfg.WESTOCK_CLI = r"C:\nonexistent\westock-data\scripts\index.js"
        try:
            self.assertIsNone(self.sp.fetch_market_breadth_tencent_skill())
        finally:
            _cfg.WESTOCK_CLI = saved


if __name__ == "__main__":
    unittest.main(verbosity=2)
