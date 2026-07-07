import os, sys, tempfile, sqlite3
from pathlib import Path
import a_stock_spider as A
from a_stock_spider import AStockSpider, MarketNewsSpider, CircuitBreaker
from data_storage import ChemDatabase

fails = []
def check(name, cond):
    print(("PASS" if cond else "FAIL"), "-", name)
    if not cond:
        fails.append(name)

# 隔离网络：所有 _fetch 强制返回 None，验证失败路径行为
A.MarketNewsSpider._fetch = lambda self, *a, **k: None

# ---- P0: 无 demo，失败返回 None/[]
sp = AStockSpider()
sp._fetch = lambda *a, **k: None
check("P0 index -> None on fail", sp.fetch_market_overview() is None)
check("P0 breadth -> None on fail", sp.fetch_market_breadth() is None)
check("P0 north -> None on fail", sp.fetch_north_flow() is None)
check("P0 sector -> None on fail", sp.fetch_sector_rankings(3) is None)
mn = MarketNewsSpider()
mn._fetch = lambda *a, **k: None
check("P0 news -> [] on fail", mn.fetch_news() == [])
check("P0 _demo_market removed", not hasattr(sp, "_demo_market"))
check("P0 _demo_news removed", not hasattr(MarketNewsSpider, "_demo_news"))
check("P0 _demo_breadth removed", not hasattr(sp, "_demo_breadth"))

# ---- P3: 熔断
cb = CircuitBreaker(fail_threshold=2, cooldown=1)
check("P3 allow initially", cb.allow())
cb.record_failure()
check("P3 allow after 1 fail", cb.allow())
cb.record_failure()
check("P3 blocked after threshold", not cb.allow())

# ---- P1: 溯源落库
tmp = os.path.join(tempfile.gettempdir(), "phase1_test.db")
if os.path.exists(tmp):
    os.remove(tmp)
db = ChemDatabase(db_path=Path(tmp))
analysis = {
    "date": "2026-07-06", "source": "eastmoney",
    "fetched_at": "2026-07-07T16:00:00", "data_complete": False,
    "indices": None, "breadth": None, "north_flow": None,
    "sectors": None, "indicators": [], "news": [],
}
rid = db.save_market_snapshot(analysis)
check("P1 snapshot saved id>0", rid > 0)
with sqlite3.connect(tmp) as c:
    row = c.execute(
        "SELECT source,fetched_at,data_complete,indices FROM stock_market_snapshot WHERE id=?",
        (rid,)).fetchone()
check("P1 source stored", row[0] == "eastmoney")
check("P1 fetched_at stored", bool(row[1]))
check("P1 data_complete=0", row[2] == 0)

# ---- P1: 聚合层溯源元数据（全失败路径）
sp2 = AStockSpider()
sp2._fetch = lambda *a, **k: None
a = sp2.fetch_previous_trading_day_analysis()
check("P1 analysis has source", a.get("source") == "eastmoney")
check("P1 analysis has fetched_at", bool(a.get("fetched_at")))
check("P1 analysis data_complete False", a.get("data_complete") == False)
check("P1 analysis indices None", a.get("indices") is None)

print("\n==== RESULT:", "ALL PASS ====" if not fails else ("FAILURES: " + ", ".join(fails)))
sys.exit(1 if fails else 0)
