"""
阶段三验证：trading_day 判断 + run_daily 在非交易日跳过 / 交易日触发。
无真实 API 依赖，纯逻辑断言。
"""
import sys
import types
from datetime import date

sys.path.insert(0, ".")

import trading_day

passed = 0


def check(cond, msg):
    global passed
    assert cond, "FAIL: " + msg
    passed += 1


# ---------- trading_day ----------
# 2026-07-07 是周二 -> 交易日
check(trading_day.is_trading_day(date(2026, 7, 7)) is True, "2026-07-07 周二应为交易日")
# 周末
check(trading_day.is_trading_day(date(2026, 7, 11)) is False, "2026-07-11 周六非交易日")
check(trading_day.is_trading_day(date(2026, 7, 12)) is False, "2026-07-12 周日非交易日")
# 法定节假日（在近似集合内）
check(trading_day.is_trading_day(date(2026, 10, 1)) is False, "2026-10-01 国庆休市")
check(trading_day.is_trading_day(date(2026, 1, 1)) is False, "2026-01-01 元旦休市")
# next_trading_day
check(trading_day.next_trading_day(date(2026, 7, 11)) == date(2026, 7, 13),
      "周六的下一交易日=周一 7-13")
nxt = trading_day.next_trading_day(date(2026, 10, 1))
check(trading_day.is_trading_day(nxt), "国庆后返回的必为交易日")

# ---------- run_daily：非交易日跳过 ----------
import run_daily

called = {"n": 0}


def fake_send():
    called["n"] += 1
    return True


run_daily.stock_mail_plugin = types.SimpleNamespace(send_enhanced=fake_send)

orig = trading_day.is_trading_day
# 强制非交易日
trading_day.is_trading_day = lambda d=None: False
rc = run_daily.main()
trading_day.is_trading_day = orig
check(rc == 0, "非交易日 main 返回 0")
check(called["n"] == 0, "非交易日不调用 send_enhanced")

# 强制交易日
trading_day.is_trading_day = lambda d=None: True
rc = run_daily.main()
trading_day.is_trading_day = orig
check(rc == 0, "交易日 main 返回 0")
check(called["n"] == 1, "交易日调用一次 send_enhanced")

# ---------- 汇总 ----------
print("PHASE3 TESTS PASSED: %d" % passed)
