# -*- coding: utf-8 -*-
"""
数据源解析静态验证（不联网，用真实接口返回体 mock _fetch）
===========================================================
固化阶段三实测修复的 3 个数据源 bug：
  1) 东方财富 clist 接口已从 data.eastmoney.com 迁移到 push2.eastmoney.com
     （旧前缀返回 404），base_url 已改；本测试验证 push2 返回体解析正确。
  2) 指数改为腾讯 qt.gtimg.cn 优先、东方财富兜底；
     腾讯行情字符串字段索引曾取错（把今开当涨跌幅），已修正，本测试验证。
  3) 涨跌分布 / 板块解析逻辑对 push2 真实 JSON 正确。

用真实抓取过的返回体（2026-07-07 收盘）作 fixture，确保"解析层"对真实数据无误。
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import unittest.mock as mock
from a_stock_spider import AStockSpider

# 真实腾讯返回体（2026-07-07 收盘）
TENCENT_RAW = (
    'v_sh000001="1~上证指数~000001~3990.24~4041.24~4019.49~514453091~0~0~0.00~'
    '0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~0~0.00~'
    '0~~20260707161401~-51.00~-1.26~4028.51~3971.71~3990.24/514453091/1196371087894~";'
)
# 真实 push2 clist 返回体（涨跌分布，m:0 前缀）
PUSH2_BREADTH = (
    '{"rc":0,"rt":6,"svr":1,"lt":1,"full":1,"dlmkts":"","dsc":"0",'
    '"data":{"total":5871,"diff":['
    '{"f2":17.02,"f3":25.06,"f12":"920527","f14":"N华之杰"},'
    '{"f2":46.14,"f3":20.0,"f12":"688432","f14":"N威迈斯"},'
    '{"f2":10.5,"f3":-3.2,"f12":"600000","f14":"浦发银行"}]}}'
)
# 真实 push2 clist 返回体（板块，m:90 前缀）
PUSH2_SECTOR = (
    '{"rc":0,"rt":6,"svr":1,"lt":1,"full":1,"dlmkts":"","dsc":"0",'
    '"data":{"total":496,"diff":['
    '{"f2":2821.55,"f3":2.93,"f4":80.45,"f12":"BK1348","f14":"贵金属"},'
    '{"f2":11230.67,"f3":2.88,"f4":314.81,"f12":"BK1328","f14":"小金属"},'
    '{"f2":2196.86,"f3":-1.5,"f4":-33.0,"f12":"BK0733","f14":"银行"}]}}'
)

PASS = 0
FAIL = 0


def check(cond, msg):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  \u2713 [PASS] " + msg)
    else:
        FAIL += 1
        print("  \u2717 [FAIL] " + msg)


def _make_spider():
    sp = AStockSpider()

    def fake_fetch(url, breaker=None, **kw):
        fs = (kw.get("params") or {}).get("fs", "")
        if "qt.gtimg" in url:
            return TENCENT_RAW
        if "clist" in url and fs.startswith("m:0"):
            return PUSH2_BREADTH
        if "clist" in url:
            return PUSH2_SECTOR
        return None

    sp._fetch = fake_fetch
    return sp


def test_parse():
    print("=== 数据源解析静态验证（真实返回体，不联网）===")
    sp = _make_spider()

    # 1) 指数（腾讯优先）
    idx = sp.fetch_market_overview()
    check(idx is not None, "指数解析非空")
    if idx:
        # 腾讯返回体的 code 字段不带市场前缀（如 "000001"），下游以 name 为准
        sh = [x for x in idx if x["name"] == "\u4e0a\u8bc1\u6307\u6570"]
        check(sh and abs(sh[0]["price"] - 3990.24) < 0.01,
              "上证指数价格解析正确 (3990.24)")
        check(sh and abs(sh[0]["chg_pct"] - (-1.26)) < 0.01,
              "上证指数涨跌幅解析正确 (-1.26%)，字段索引已修复")
        check(sh and abs(sh[0]["high"] - 4028.51) < 0.01,
              "上证指数最高解析正确 (4028.51)")
        check(sh and abs(sh[0]["low"] - 3971.71) < 0.01,
              "上证指数最低解析正确 (3971.71)")

    # 2) 涨跌分布（push2 前缀）
    br = sp.fetch_market_breadth()
    check(br is not None, "涨跌分布解析非空（push2 前缀修复后）")
    if br:
        check(br["total"] == 3, "涨跌分布总数解析正确 (3)")
        check(br["up"] == 2 and br["down"] == 1, "涨跌家数解析正确 (涨2跌1)")
        check(br["top_gainers"][0]["name"] == "N华之杰", "涨幅榜首解析正确")

    # 3) 板块（push2 前缀）
    secs = sp.fetch_sector_rankings(3)
    check(secs is not None, "板块解析非空（push2 前缀修复后）")
    if secs:
        check(secs[0]["sector"] == "\u8d35\u91d1\u5c5e", "板块榜首解析正确 (贵金属)")
        check(abs(secs[0]["chg"] - 2.93) < 0.01, "板块涨幅解析正确 (2.93%)")


if __name__ == "__main__":
    test_parse()
    print("\n========================================")
    print("数据源解析验证: PASS=%d  FAIL=%d" % (PASS, FAIL))
    print("========================================")
    sys.exit(1 if FAIL else 0)
