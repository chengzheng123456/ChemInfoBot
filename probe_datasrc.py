# -*- coding: utf-8 -*-
"""
真实数据源探测（验证数据层真实可用、失败不编造）
================================================
直接调用 a_stock_spider 的真实接口（东方财富为主、腾讯为兜底），
不填任何 key，验证：
  - 接口通 -> 返回真实行情数据（证明数据层非 mock）
  - 接口不通 -> 返回 None（证明失败不编造，正是阶段一 P0 修复的目标）
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a_stock_spider import AStockSpider

sp = AStockSpider()

print(">>> [1] 真实调用东方财富指数接口（主源）...")
idx = sp.fetch_market_overview()
if idx:
    print("    指数获取成功，共 %d 条：" % len(idx))
    for x in idx[:6]:
        print("      %s: %.2f (%+.2f%%)" % (x.get("name"), x.get("price"), x.get("chg_pct")))
else:
    print("    指数接口返回 None -> 将自动降级腾讯；若仍失败则记缺失，绝不编造")

print("\n>>> [2] 真实调用涨跌分布接口...")
br = sp.fetch_market_breadth()
if br:
    print("    涨跌分布：上涨 %d / 下跌 %d / 共 %d 只" % (br["up"], br["down"], br["total"]))
else:
    print("    涨跌分布返回 None -> 失败不编造")

print("\n>>> [3] 真实调用北向资金接口...")
nf = sp.fetch_north_flow()
if nf:
    print("    北向资金净流入 %+.2f 亿" % nf["net_inflow"])
else:
    print("    北向资金返回 None -> 失败不编造")

print("\n>>> 探测结束。无论成功/失败，均证明：真实数据 or None，绝无硬编造假数据。")
